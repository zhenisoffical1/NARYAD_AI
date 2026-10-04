"""Пульт оператора демо (CLAUDE.md, раздел 10). Работает только при DEMO_MODE=true.

Без входа: пульт открывают на ноутбуке у проектора, а телефоны входят по QR. На боевом
сервере DEMO_MODE выключен, и все эти адреса отвечают 404.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import employee_out
from app.config import settings
from app.db import get_session
from app.errors import Conflict, NotFound
from app.models import Employee, Order
from app.models.base import utcnow
from app.models.enums import (
    ACTIVE_STATUSES,
    PRIORITY_RANK,
    STATUS_LABELS,
    OrderStatus,
    Priority,
    Role,
)
from app.schemas.auth import TokenResponse
from app.security import create_access_token
from app.services.deadlines import check_deadlines
from app.services.notifications.live import LiveEvent, commit_and_publish, queue_event
from app.services.notifications.notify import notify
from app.services.orders import local_time
from app.services.people import shift_people
from seed.demo import build_scene, get_history_end


def demo_only() -> None:
    if not settings.demo_mode:
        raise NotFound("Страница не найдена.")


router = APIRouter(prefix="/demo", tags=["Демо"], dependencies=[Depends(demo_only)])

ALL_ROLES = frozenset(Role)


class DemoAccount(BaseModel):
    id: int
    login: str
    full_name: str
    short_name: str
    role: Role
    specialty: str | None
    state: str | None  # для исполнителей: free / busy / queue / off_shift
    telegram_linked: bool


class DemoOrder(BaseModel):
    id: int
    number: int
    status: OrderStatus
    status_label: str
    priority: Priority
    equipment: str
    assignee: str | None
    deadline_local: str
    overdue: bool
    can_escalate: bool


class DemoState(BaseModel):
    llm: str
    telegram: bool
    telegram_bot: str | None
    public_url: str
    accounts: list[DemoAccount]
    orders: list[DemoOrder]


class Fired(BaseModel):
    rules: list[str]


class DemoLogin(BaseModel):
    login: str


class DemoNotify(BaseModel):
    employee_id: int


async def _broadcast_reset(session: AsyncSession) -> None:
    """Всем открытым экранам — перечитать данные (наряды, люди, счётчики)."""
    queue_event(session, LiveEvent(type="demo.reset", payload={}, roles=ALL_ROLES))


@router.get("", response_model=DemoState, summary="Состояние сцены для пульта")
async def state(session: AsyncSession = Depends(get_session)) -> DemoState:
    people = {p.employee.id: p.state for p in await shift_people(session)}
    employees = await session.scalars(
        select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.full_name)
    )
    accounts = [
        DemoAccount(
            id=e.id,
            login=e.login,
            full_name=e.full_name,
            short_name=e.short_name,
            role=e.role,
            specialty=e.specialty,
            state=people.get(e.id),
            telegram_linked=e.telegram_chat_id is not None,
        )
        for e in employees
    ]

    since = await get_history_end(session)
    stmt = (
        select(Order)
        .where(Order.status.in_(ACTIVE_STATUSES))
        .options(selectinload(Order.equipment), selectinload(Order.assignee))
    )
    if since is not None:
        stmt = stmt.where(Order.created_at >= since)
    now = utcnow()
    orders = sorted(
        await session.scalars(stmt), key=lambda o: (PRIORITY_RANK[o.priority], o.number)
    )
    return DemoState(
        llm="mock" if settings.llm_mock else settings.llm_model,
        telegram=bool(settings.telegram_bot_token),
        telegram_bot=settings.telegram_bot_username,
        public_url=settings.public_url,
        accounts=accounts,
        orders=[
            DemoOrder(
                id=o.id,
                number=o.number,
                status=o.status,
                status_label=STATUS_LABELS[o.status],
                priority=o.priority,
                equipment=o.equipment.name,
                assignee=o.assignee.short_name if o.assignee else None,
                deadline_local=local_time(o.deadline_at),
                overdue=o.deadline_at < now,
                can_escalate=o.status == OrderStatus.ISSUED,
            )
            for o in orders
        ],
    )


@router.post("/reset", response_model=Fired, summary="Пересоздать демо-смену")
async def reset(session: AsyncSession = Depends(get_session)) -> Fired:
    try:
        count = await build_scene(session)
    except RuntimeError as exc:
        raise Conflict("Нет истории для сцены. Выполните полный сид: python -m seed") from exc
    await _broadcast_reset(session)
    await commit_and_publish(session)
    return Fired(rules=[f"scene:{count}"])


async def _scene_order(session: AsyncSession, order_id: int) -> Order:
    order = await session.get(Order, order_id)
    if order is None:
        raise NotFound("Наряд не найден — обновите пульт.")
    return order


async def _run_checks(session: AsyncSession, order: Order, now: datetime) -> Fired:
    fired = await check_deadlines(session, now=now, order_ids=[order.id])
    queue_event(
        session,
        LiveEvent(
            type="order.updated",
            payload={"order_id": order.id, "number": order.number, "change": "deadline"},
            roles=frozenset({Role.MASTER, Role.BOSS, Role.ADMIN}),
            user_ids=frozenset({order.assignee_id} if order.assignee_id else set()),
        ),
    )
    await commit_and_publish(session)
    return Fired(rules=[f.rule for f in fired])


@router.post("/orders/{order_id}/overdue", response_model=Fired, summary="Промотать до просрочки")
async def make_overdue(order_id: int, session: AsyncSession = Depends(get_session)) -> Fired:
    """Срок наряда сдвигается на 5 минут назад — планировщик сразу шлёт сообщение о просрочке."""
    order = await _scene_order(session, order_id)
    if order.status not in ACTIVE_STATUSES or order.status in (
        OrderStatus.DONE,
        OrderStatus.AI_REVIEW,
    ):
        raise Conflict(f"Наряд №{order.number} уже исполнен — просрочить нечего.")
    now = utcnow()
    order.deadline_at = now - timedelta(minutes=5)
    order.reminder_sent_at = now  # напоминание «до срока» здесь уже не к месту
    order.overdue_notified_at = None
    order.boss_notified_at = None
    return await _run_checks(session, order, now)


@router.post(
    "/orders/{order_id}/unaccepted",
    response_model=Fired,
    summary="Промотать до эскалации «не принят»",
)
async def make_unaccepted(order_id: int, session: AsyncSession = Depends(get_session)) -> Fired:
    order = await _scene_order(session, order_id)
    if order.status != OrderStatus.ISSUED:
        raise Conflict(f"Наряд №{order.number} уже принят — эскалировать нечего.")
    now = utcnow()
    limit = (
        settings.unaccepted_emergency_min
        if order.priority == Priority.EMERGENCY
        else settings.unaccepted_min
    )
    order.issued_at = now - timedelta(minutes=limit)
    order.escalated_at = None
    return await _run_checks(session, order, now)


@router.post("/notify", status_code=204, summary="Тестовое уведомление")
async def test_notification(body: DemoNotify, session: AsyncSession = Depends(get_session)) -> None:
    employee = await session.get(Employee, body.employee_id)
    if employee is None:
        raise NotFound("Сотрудник не найден.")
    await notify(
        session,
        employee_id=employee.id,
        kind="test",
        title="Проверка связи",
        body=f"{employee.full_name}, уведомления доходят. Время: {local_time(utcnow())}.",
    )
    await commit_and_publish(session)


@router.post("/login", response_model=TokenResponse, summary="Вход по QR на демо")
async def demo_login(
    body: DemoLogin, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    user = await session.scalar(
        select(Employee).where(Employee.login == body.login.strip().lower())
    )
    if user is None or not user.is_active:
        raise NotFound("Нет такой учётной записи в демо.")
    return TokenResponse(
        access_token=create_access_token(user.id, user.role), user=employee_out(user)
    )
