"""Проверка закрытого наряда: правила → соответствие работ → фото → итог → отчёты.

Запускается сразу после «Исполнено» (наряд уже в «Проверка ИИ»). Каждый шаг виден в
интерфейсе через WebSocket. Если вердикт «требует доработки» — наряд возвращается
исполнителю автоматически; иначе ждёт подтверждения мастера: финальное слово за ним.
"""

import asyncio
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import SessionLocal
from app.models import (
    AiAssessment,
    Employee,
    FaultCode,
    MaterialWriteoff,
    Order,
    OrderEvent,
    TimeNorm,
    TimeNormMaterial,
)
from app.models.base import utcnow
from app.models.enums import AssessmentStatus, OrderStatus, PhotoKind, Verdict
from app.services.llm import anonymize
from app.services.notifications.bus import bus
from app.services.notifications.live import (
    STAFF_ROLES,
    LiveEvent,
    commit_and_publish,
    queue_event,
)
from app.services.notifications.notify import notify
from app.services.state_machine import Action, apply_transition
from app.services.verification.aggregate import aggregate
from app.services.verification.facts import ClosureFacts, MaterialFact
from app.services.verification.llm_check import works_match
from app.services.verification.photos import check_photos, compare_pair, compare_photos
from app.services.verification.rules import run_rules
from app.services.verification.texts import VERDICT_LABELS, master_report, worker_report

log = logging.getLogger(__name__)

STEPS = ("completeness", "time", "materials", "works_match", "photos")


async def _ready[T](value: T) -> T:
    return value


async def _load(session: AsyncSession, order_id: int) -> Order | None:
    return await session.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.photos),
            selectinload(Order.equipment),
            selectinload(Order.writeoffs).selectinload(MaterialWriteoff.material),
            selectinload(Order.fault_code)
            .selectinload(FaultCode.norm)
            .selectinload(TimeNorm.materials)
            .selectinload(TimeNormMaterial.material),
            selectinload(Order.events),
        )
        .execution_options(populate_existing=True)
    )


def build_facts(order: Order) -> ClosureFacts:
    """Факты о закрытии из наряда — общий вход для правил и LLM."""
    assert order.fault_code is not None and order.done_at is not None
    norm = order.fault_code.norm
    norm_by_material: dict[int, Decimal] = (
        {line.material_id: line.quantity for line in norm.materials} if norm else {}
    )
    paused = 0
    pause_started = None
    for event in order.events:
        if event.to_status == OrderStatus.PAUSED:
            pause_started = event.created_at
        elif pause_started and event.from_status == OrderStatus.PAUSED:
            paused += int((event.created_at - pause_started).total_seconds() // 60)
            pause_started = None

    return ClosureFacts(
        number=order.number,
        order_type=order.type,
        priority=order.priority,
        equipment=order.equipment.name,
        equipment_type=order.equipment.type,
        description=order.description,
        works_done=order.works_done or "",
        fault_code=order.fault_code.code,
        fault_name=order.fault_code.name,
        norm_hours=order.norm_hours or (norm.norm_hours if norm else None),
        norm_materials=tuple(
            (line.material.name, line.material.unit, line.quantity)
            for line in (norm.materials if norm else [])
        ),
        no_materials=order.no_materials,
        materials=tuple(
            MaterialFact(
                name=w.material.name,
                unit=w.unit,
                quantity=w.quantity,
                category=w.material.category,
                norm_quantity=norm_by_material.get(w.material_id),
            )
            for w in order.writeoffs
        ),
        after_photos=sum(1 for p in order.photos if p.kind == PhotoKind.AFTER),
        before_photos=sum(1 for p in order.photos if p.kind == PhotoKind.BEFORE),
        issued_at=order.issued_at or order.created_at,
        started_at=order.started_at,
        done_at=order.done_at,
        deadline_at=order.deadline_at,
        paused_minutes=paused,
        comment=order.closing_comment,
    )


async def _progress(order: Order, step: str, status: str) -> None:
    await bus.publish(
        LiveEvent(
            type="assessment.progress",
            payload={"order_id": order.id, "step": step, "status": status},
            roles=STAFF_ROLES,
            user_ids=frozenset({order.assignee_id} if order.assignee_id else set()),
        )
    )


async def run_verification(order_id: int) -> None:
    """Точка входа фоновой задачи. Сама открывает сессию и сама сообщает об ошибке мастеру."""
    async with SessionLocal() as session:
        try:
            await _verify(session, order_id)
        except Exception:
            log.exception("ИИ-проверка наряда %s не выполнена", order_id)
            await session.rollback()
            await _mark_failed(session, order_id)


async def _verify(session: AsyncSession, order_id: int) -> None:
    order = await _load(session, order_id)
    if order is None or order.status != OrderStatus.AI_REVIEW or order.fault_code is None:
        return

    assessment = AiAssessment(
        order_id=order.id,
        status=AssessmentStatus.RUNNING,
        mode="mock" if settings.llm_mock else "llm",
        created_at=utcnow(),
    )
    session.add(assessment)
    await session.commit()

    facts = build_facts(order)
    checks = run_rules(facts)
    for check in checks:
        await _progress(order, check.key, check.status)

    # Детерминированная часть фото — до вызова модели: дубль или старый снимок ловится без неё
    photo = await check_photos(session, order)
    pair = compare_pair(order)
    names = list(await session.scalars(select(Employee.full_name)))
    # Два вызова модели — параллельно, чтобы уложиться в 15 секунд
    works, photo = await asyncio.gather(
        works_match(facts, names),
        compare_photos(
            photo,
            pair,
            anonymize(facts.description, names),
            anonymize(facts.works_done, names),
        )
        if pair
        else _ready(photo),
    )
    checks.append(works.check)
    await _progress(order, "works_match", works.check.status)
    checks.append(photo.check)
    await _progress(order, "photos", photo.check.status)
    assessment.mode = "llm" if "llm" in (works.source, photo.source) else "mock"

    result = aggregate(checks, min(works.confidence, photo.confidence))
    now = utcnow()
    assessment.status = AssessmentStatus.DONE
    assessment.verdict = result.verdict
    assessment.score_0_100 = result.score
    assessment.score_1_5 = photo.score_1_5
    assessment.confidence = round(result.confidence, 2)
    assessment.needs_master_review = result.needs_master_review
    assessment.checks = [c.as_dict() for c in checks]
    assessment.explanation_worker = worker_report(facts, checks, result)
    assessment.explanation_master = master_report(facts, checks, result)
    assessment.finished_at = now

    verdict_text = VERDICT_LABELS[result.verdict] if result.verdict else "нужна проверка мастером"
    session.add(
        OrderEvent(
            order_id=order.id,
            action="ai_checked",
            data={"verdict": result.verdict.value if result.verdict else None,
                  "score": result.score},
            comment=f"{verdict_text}, {result.score} из 100",
            created_at=now,
        )
    )  # fmt: skip

    if result.verdict == Verdict.REWORK:
        reasons = [c.detail for c in checks if c.critical] or [
            c.detail for c in checks if c.status in ("warn", "fail")
        ]
        reason = reasons[0] if reasons else "Требует доработки"
        await apply_transition(
            session,
            order,
            Action.SEND_TO_REWORK,
            actor=None,
            reason=f"Вердикт ИИ: {reason}"[:200],
            now=now,
        )
        if order.assignee_id:
            await notify(
                session,
                employee_id=order.assignee_id,
                kind="order_rework",
                title=f"Наряд №{order.number} — нужна доработка",
                body=reason,
                order_id=order.id,
            )
        await notify(
            session,
            employee_id=order.master_id,
            kind="ai_rework",
            title=f"Наряд №{order.number} возвращён ИИ на доработку",
            body=reason,
            order_id=order.id,
        )
    else:
        if order.assignee_id:
            await notify(
                session,
                employee_id=order.assignee_id,
                kind="ai_checked",
                title=f"Наряд №{order.number} проверен: {result.score} из 100",
                body=verdict_text.capitalize() + ". Подробный отчёт — в карточке наряда.",
                order_id=order.id,
            )
        await notify(
            session,
            employee_id=order.master_id,
            kind="ai_checked",
            title=f"Наряд №{order.number}: {verdict_text}, {result.score} из 100",
            body="Подтвердите закрытие или измените оценку.",
            order_id=order.id,
        )

    queue_event(
        session,
        LiveEvent(
            type="assessment.done",
            payload={
                "order_id": order.id,
                "number": order.number,
                "verdict": result.verdict.value if result.verdict else None,
                "score": result.score,
            },
            roles=STAFF_ROLES,
            user_ids=frozenset({order.assignee_id} if order.assignee_id else set()),
        ),
    )
    await commit_and_publish(session)


async def _mark_failed(session: AsyncSession, order_id: int) -> None:
    order = await session.get(Order, order_id)
    if order is None:
        return
    running = await session.scalar(
        select(AiAssessment)
        .where(AiAssessment.order_id == order_id, AiAssessment.status == AssessmentStatus.RUNNING)
        .order_by(AiAssessment.id.desc())
    )
    if running is not None:
        running.status = AssessmentStatus.FAILED
        running.finished_at = utcnow()
    await notify(
        session,
        employee_id=order.master_id,
        kind="ai_failed",
        title=f"Наряд №{order.number}: ИИ-проверка не выполнена",
        body="Проверьте закрытие вручную и подтвердите или верните на доработку.",
        order_id=order.id,
    )
    queue_event(
        session,
        LiveEvent(
            type="assessment.done",
            payload={"order_id": order.id, "number": order.number, "verdict": None},
            roles=STAFF_ROLES,
            user_ids=frozenset({order.assignee_id} if order.assignee_id else set()),
        ),
    )
    await commit_and_publish(session)
