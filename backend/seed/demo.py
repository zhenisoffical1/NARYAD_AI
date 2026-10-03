"""Демо-сцена «смена сейчас» для защиты (CLAUDE.md, раздел 10).

Пересоздаётся за доли секунды: удаляются всё, что появилось после конца истории,
и заново раскладываются наряды текущей смены. История за 3 месяца не трогается.
"""

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import (
    AiAssessment,
    AppState,
    Employee,
    Equipment,
    FaultCode,
    Material,
    MaterialWriteoff,
    Notification,
    Order,
    OrderEvent,
    TimeNorm,
    TimeNormMaterial,
)
from app.models.base import utcnow
from app.models.enums import AssessmentStatus, OrderStatus, OrderType, Priority, Role, Shift
from app.services.verification.aggregate import aggregate
from app.services.verification.facts import CheckResult, ClosureFacts, MaterialFact
from app.services.verification.llm_check import mock_works_match
from app.services.verification.rules import run_rules
from app.services.verification.texts import master_report, worker_report

S = OrderStatus
HISTORY_END_KEY = "history_end"

DEMO_MASTER = "master1"
OFF_TODAY = {"nurpeisov"}  # отгул — показывает серый статус «не на смене»


@dataclass(frozen=True)
class SceneOrder:
    login: str
    inv: str
    priority: Priority
    description: str
    path: tuple[tuple[str, S, int], ...]  # (действие, статус, минут назад)
    fault: str | None = None
    works: str | None = None
    materials: tuple[tuple[str, float], ...] = ()
    deadline_in: int = 180  # минут от «сейчас»
    stopped: bool = False
    reason: str | None = None


SCENE = (
    # Закрыт в начале смены — хорошая работа слесаря, которого ИИ потом предложит на насос
    SceneOrder(
        "akhmetov", "ОБ-006", Priority.PLANNED, "ППР по графику: насос шламовый ГрАТ-1400",
        (("accept", S.ACCEPTED, 300), ("start", S.IN_PROGRESS, 290), ("complete", S.DONE, 200),
         ("begin_review", S.AI_REVIEW, 200), ("close", S.CLOSED, 180)),
        fault="С-02", works="Плановый осмотр, протяжка крепежа, смазка узлов",
        materials=(("Смазка Литол-24", 0.5), ("Смазка Солидол Ж", 0.3)), deadline_in=600,
    ),
    SceneOrder(
        "kovalchuk", "КТ-001", Priority.PLANNED, "ППР по графику: конвейер К-1",
        (("accept", S.ACCEPTED, 280), ("start", S.IN_PROGRESS, 270), ("complete", S.DONE, 190),
         ("begin_review", S.AI_REVIEW, 190), ("close", S.CLOSED, 150)),
        fault="С-02", works="ППР: ревизия узлов, замена смазки, проверка зазоров",
        materials=(("Смазка Литол-24", 0.6),), deadline_in=600,
    ),
    # Электрик в работе
    SceneOrder(
        "abenov", "КТ-002", Priority.HIGH,
        "Двигатель привода конвейера К-2 греется, срабатывает тепловая защита",
        (("accept", S.ACCEPTED, 52), ("start", S.IN_PROGRESS, 45)), deadline_in=150, stopped=True,
    ),
    # Сварщик в работе
    SceneOrder(
        "sidorenko", "ДР-004", Priority.NORMAL, "Трещина на раме питателя у опоры привода",
        (("accept", S.ACCEPTED, 70), ("start", S.IN_PROGRESS, 60)), deadline_in=200,
    ),
    # Слесарь с очередью из двух нарядов
    SceneOrder(
        "baizhanov", "ДР-005", Priority.NORMAL, "Ослаб крепёж опоры грохота, повышенная вибрация",
        (("queue", S.QUEUED, 35),), deadline_in=240,
    ),
    SceneOrder(
        "baizhanov", "ДР-006", Priority.PLANNED, "Плановая замена фильтроэлемента маслостанции",
        (("queue", S.QUEUED, 20),), deadline_in=420,
    ),
    # Принят, но ещё не начат
    SceneOrder(
        "seitkaziev", "ОБ-001", Priority.NORMAL, "Узел работает всухую, скрип у подшипника цапфы",
        (("accept", S.ACCEPTED, 12),), deadline_in=200,
    ),
    # Отклонён — ждёт решения мастера
    SceneOrder(
        "omarov", "ОБ-004", Priority.NORMAL, "Ложные срабатывания датчика уровня в ванне",
        (("reject", S.REJECTED, 15),), deadline_in=180, reason="нет допуска",
    ),
    # Исполнен — ИИ проверил, ждёт подтверждения мастера
    SceneOrder(
        "omarov", "ОБ-003", Priority.PLANNED, "Плановая замена контакторов в шкафу управления",
        (("accept", S.ACCEPTED, 150), ("start", S.IN_PROGRESS, 140), ("complete", S.DONE, 9),
         ("begin_review", S.AI_REVIEW, 9)),
        fault="Э-02", works="Заменены контакторы КМИ-32 в шкафу управления, протянуты клеммы, "
        "проверена работа схемы", materials=(("Контактор КМИ-32", 2),), deadline_in=60,
    ),
)  # fmt: skip

STATUS_FIELD = {
    S.QUEUED: "queued_at",
    S.ACCEPTED: "accepted_at",
    S.REJECTED: "rejected_at",
    S.IN_PROGRESS: "started_at",
    S.DONE: "done_at",
    S.AI_REVIEW: "review_at",
    S.CLOSED: "closed_at",
}


async def get_history_end(session: AsyncSession) -> datetime | None:
    state = await session.get(AppState, HISTORY_END_KEY)
    return datetime.fromisoformat(state.value) if state else None


async def set_history_end(session: AsyncSession, at: datetime) -> None:
    state = await session.get(AppState, HISTORY_END_KEY)
    if state is None:
        session.add(AppState(key=HISTORY_END_KEY, value=at.isoformat()))
    else:
        state.value = at.isoformat()


async def clear_scene(session: AsyncSession, history_end: datetime) -> None:
    ids = list(await session.scalars(select(Order.id).where(Order.created_at >= history_end)))
    if ids:
        await session.execute(delete(Order).where(Order.id.in_(ids)))
    await session.execute(delete(Notification).where(Notification.created_at >= history_end))
    # Удалённые строки не должны остаться в памяти сессии: новые записи могут получить те же id
    session.expunge_all()
    for order_id in ids:
        shutil.rmtree(settings.media_dir / "orders" / str(order_id), ignore_errors=True)


async def build_scene(session: AsyncSession, now: datetime | None = None) -> int:
    """Сбросить и разложить демо-сцену. Возвращает число нарядов в сцене."""
    now = now or utcnow()
    history_end = await get_history_end(session)
    if history_end is None:
        raise RuntimeError("Сначала выполните полный сид: python -m seed")
    await clear_scene(session, history_end)

    people = {e.login: e for e in await session.scalars(select(Employee))}
    await session.execute(update(Employee).values(on_shift=False))
    for e in people.values():
        if e.role == Role.WORKER and e.shift == Shift.DAY and e.login not in OFF_TODAY:
            e.on_shift = True

    equipment = {e.inv_number: e for e in await session.scalars(select(Equipment))}
    faults = {
        f.code: f
        for f in await session.scalars(
            select(FaultCode).options(
                selectinload(FaultCode.norm)
                .selectinload(TimeNorm.materials)
                .selectinload(TimeNormMaterial.material)
            )
        )
    }
    materials = {m.name: m for m in await session.scalars(select(Material))}
    master = people[DEMO_MASTER]
    number = int(await session.scalar(select(Order.number).order_by(Order.number.desc())) or 0)

    for spec in SCENE:
        number += 1
        worker = people[spec.login]
        eq = equipment[spec.inv]
        first_minutes = max((m for _, _, m in spec.path), default=10) + 5
        created = now - timedelta(minutes=first_minutes)
        fault = faults.get(spec.fault) if spec.fault else None
        order = Order(
            number=number,
            type=OrderType.PLANNED if spec.priority == Priority.PLANNED else OrderType.UNPLANNED,
            priority=spec.priority,
            status=S.ISSUED,
            description=spec.description,
            section_id=eq.section_id,
            equipment_id=eq.id,
            assignee_id=worker.id,
            brigade_id=worker.brigade_id,
            master_id=master.id,
            deadline_at=now + timedelta(minutes=spec.deadline_in),
            norm_hours=fault.norm.norm_hours if fault and fault.norm else None,
            equipment_stopped=spec.stopped,
            created_at=created,
            issued_at=created,
            updated_at=now,
        )
        events = [
            OrderEvent(action="create", to_status=S.ISSUED, actor_id=master.id, created_at=created)
        ]
        for action, status, minutes_ago in spec.path:
            at = now - timedelta(minutes=minutes_ago)
            actor = None if action == "begin_review" else (master if action == "close" else worker)
            events.append(
                OrderEvent(
                    action=action,
                    from_status=order.status,
                    to_status=status,
                    actor_id=actor.id if actor else None,
                    reason=spec.reason if action == "reject" else None,
                    created_at=at,
                )
            )
            order.status = status
            setattr(order, STATUS_FIELD[status], at)
        order.events = events

        if spec.works and fault:
            order.works_done = spec.works
            order.fault_code_id = fault.id
            order.no_materials = not spec.materials
            order.writeoffs = [
                MaterialWriteoff(
                    material_id=materials[name].id,
                    quantity=Decimal(str(qty)),
                    unit=materials[name].unit,
                )
                for name, qty in spec.materials
            ]
        session.add(order)
        await session.flush()

        if spec.works and fault and order.done_at:
            session.add(_assessment(order, eq, fault, spec, materials))

    await set_history_end(session, history_end)
    await session.flush()
    return len(SCENE)


def _assessment(
    order: Order,
    eq: Equipment,
    fault: FaultCode,
    spec: SceneOrder,
    materials: dict[str, Material],
) -> AiAssessment:
    assert order.done_at is not None and spec.works is not None
    norm_lines = {m.material.name: m.quantity for m in fault.norm.materials} if fault.norm else {}
    facts = ClosureFacts(
        number=order.number,
        order_type=order.type,
        priority=order.priority,
        equipment=eq.name,
        equipment_type=eq.type,
        description=order.description,
        works_done=spec.works,
        fault_code=fault.code,
        fault_name=fault.name,
        norm_hours=order.norm_hours,
        norm_materials=tuple((name, materials[name].unit, qty) for name, qty in norm_lines.items()),
        no_materials=not spec.materials,
        materials=tuple(
            MaterialFact(
                name=name,
                unit=materials[name].unit,
                quantity=Decimal(str(qty)),
                category=materials[name].category,
                norm_quantity=norm_lines.get(name),
            )
            for name, qty in spec.materials
        ),
        after_photos=0,
        before_photos=0,
        issued_at=order.created_at,
        started_at=order.started_at,
        done_at=order.done_at,
        deadline_at=order.deadline_at,
    )
    checks = run_rules(facts)
    match = mock_works_match(facts)
    checks.append(match.check)
    checks.append(
        CheckResult("photos", "Фото до и после", "skip", "Фото к плановому наряду не прикладывали.")
    )
    result = aggregate(checks, match.confidence)
    return AiAssessment(
        order_id=order.id,
        status=AssessmentStatus.DONE,
        mode="mock",
        verdict=result.verdict,
        score_0_100=result.score,
        confidence=round(result.confidence, 2),
        needs_master_review=result.needs_master_review,
        explanation_worker=worker_report(facts, checks, result),
        explanation_master=master_report(facts, checks, result),
        checks=[c.as_dict() for c in checks],
        created_at=order.done_at,
        finished_at=order.done_at + timedelta(seconds=9),
    )
