"""ИИ-контроль сроков (ТЗ 6.1): напоминания, просрочки, эскалации, повторы.

Планировщик вызывает `check_deadlines` раз в 30 секунд. Каждое правило помечает в наряде,
когда сработало (`reminder_sent_at`, `overdue_notified_at`, …), поэтому одно и то же
сообщение не уходит дважды, а повтор приходит ровно через заданный интервал.

Тексты собираются из фактов наряда без LLM: сроки и фамилии должны быть точными,
а Telegram — внутренний канал предприятия, ФИО в нём допустимы.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Employee, Order, OrderEvent
from app.models.base import utcnow
from app.models.enums import (
    DEADLINE_TRACKED_STATUSES,
    PRIORITY_LABELS,
    STATUS_LABELS,
    OrderStatus,
    Priority,
    Role,
)
from app.services.notifications.notify import notify
from app.services.orders import local_time
from app.services.people import shift_people
from app.services.state_machine import STATUS_TIMESTAMP_FIELD

S = OrderStatus
MINUTE = timedelta(minutes=1)

# «участок дробления» — как в примере ТЗ; для цеха слово «участок» лишнее
SECTION_PHRASE = {
    "Дробление": "участок дробления",
    "Обогащение": "участок обогащения",
    "Конвейерный транспорт": "участок конвейерного транспорта",
    "Ремонтно-механический цех": "ремонтно-механический цех",
}


@dataclass(frozen=True, slots=True)
class Fired:
    """Что сработало — для журнала планировщика и тестов."""

    rule: str
    order_number: int


def duration(minutes: int) -> str:
    """45 → «45 мин», 135 → «2 ч 15 мин», 120 → «2 ч»."""
    hours, mins = divmod(max(minutes, 0), 60)
    if not hours:
        return f"{mins} мин"
    return f"{hours} ч {mins} мин" if mins else f"{hours} ч"


def section_phrase(name: str) -> str:
    return SECTION_PHRASE.get(name, f"участок «{name}»")


def _end(text: str) -> str:
    """Закончить предложение точкой, не удваивая её после инициала: «Ахметов Е.»."""
    return text if text.endswith(".") else f"{text}."


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


def _assignee_label(order: Order) -> str:
    if order.assignee is not None:
        return order.assignee.short_name
    if order.brigade is not None:
        return f"{order.brigade.name} (никто не взял)"
    return "не назначен"


def _status_since(order: Order) -> str:
    since: datetime | None = getattr(order, STATUS_TIMESTAMP_FIELD[order.status])
    label = STATUS_LABELS[order.status].lower()
    return f"{label} с {local_time(since)}" if since else label


async def _last_comment(session: AsyncSession, order: Order) -> str | None:
    """Последнее, что люди написали по наряду: комментарий или причина паузы/отказа."""
    event = await session.scalar(
        select(OrderEvent)
        .where(
            OrderEvent.order_id == order.id,
            OrderEvent.actor_id.is_not(None),
            or_(OrderEvent.comment.is_not(None), OrderEvent.reason.is_not(None)),
        )
        .order_by(OrderEvent.created_at.desc(), OrderEvent.id.desc())
        .limit(1)
    )
    if event is None:
        return order.comment
    return event.comment or event.reason


async def overdue_text(session: AsyncSession, order: Order, now: datetime) -> str:
    """Формат из ТЗ: «Наряд №147 просрочен на 45 мин. Дробилка КМД-1750, участок дробления.
    Исполнитель: Ахметов Е. Статус: в работе с 09:20. Последний комментарий: “…”»."""
    late = duration(_minutes(now - order.deadline_at))
    text = (
        f"Наряд №{order.number} просрочен на {late}. "
        f"{order.equipment.name}, {section_phrase(order.section.name)}. "
        f"Исполнитель: {_end(_assignee_label(order))} "
        f"Статус: {_status_since(order)}."
    )
    if comment := await _last_comment(session, order):
        text += f" Последний комментарий: “{comment.strip()}”."
    return text


async def _recipients(session: AsyncSession, order: Order) -> list[int]:
    """Исполнитель, а у бригадного наряда, который ещё никто не взял, — вся бригада.

    Отклонённый наряд ждёт решения мастера — тот, кто отказался, сообщений о нём не получает.
    """
    if order.status == S.REJECTED:
        return []
    if order.assignee_id is not None:
        return [order.assignee_id]
    if order.brigade_id is None:
        return []
    return list(
        await session.scalars(
            select(Employee.id).where(
                Employee.brigade_id == order.brigade_id,
                Employee.role == Role.WORKER,
                Employee.is_active.is_(True),
            )
        )
    )


async def suggest_free_worker(session: AsyncSession, order: Order) -> Employee | None:
    """Свободный исполнитель той же специальности, иначе — любой свободный."""
    specialty = order.assignee.specialty if order.assignee else None
    free = [
        p.employee
        for p in await shift_people(session)
        if p.state == "free" and p.employee.id != order.assignee_id
    ]
    same = [p for p in free if specialty and p.specialty == specialty]
    pool = same or free
    return await session.get(Employee, pool[0].id) if pool else None


def _due(last: datetime | None, base: datetime, every: timedelta, now: datetime) -> bool:
    """Пора ли повторить: первый раз — от `base`, дальше — от последней отправки."""
    since = max(last, base) if last else base
    return now - since >= every


async def _alarm(session: AsyncSession, order: Order, now: datetime) -> Fired | None:
    """Аварийный наряд «звонит» исполнителю каждую минуту, пока его не примут."""
    if order.priority != Priority.EMERGENCY or order.status != S.ISSUED or not order.issued_at:
        return None
    every = timedelta(minutes=settings.emergency_repeat_min)
    if not _due(order.alarm_repeated_at, order.issued_at, every, now):
        return None
    waited = duration(_minutes(now - order.issued_at))
    for employee_id in await _recipients(session, order):
        await notify(
            session,
            employee_id=employee_id,
            kind="order_alarm",
            title=f"АВАРИЙНЫЙ наряд №{order.number} ждёт ответа {waited}",
            body=f"{order.equipment.name} ({order.equipment.inv_number}). "
            f"{order.description[:160]}",
            order_id=order.id,
            urgent=True,
            feed=False,
        )
    order.alarm_repeated_at = now
    return Fired("alarm", order.number)


async def _escalate(session: AsyncSession, order: Order, now: datetime) -> Fired | None:
    """Не принят за 10 мин (аварийный — за 3) — мастеру, с кандидатом на замену."""
    if order.status != S.ISSUED or not order.issued_at:
        return None
    limit = (
        settings.unaccepted_emergency_min
        if order.priority == Priority.EMERGENCY
        else settings.unaccepted_min
    )
    if now - order.issued_at < timedelta(minutes=limit):
        return None
    if order.escalated_at and now - order.escalated_at < timedelta(minutes=settings.repeat_min):
        return None

    waited = duration(_minutes(now - order.issued_at))
    body = (
        f"{PRIORITY_LABELS[order.priority]}. {order.equipment.name}, "
        f"{section_phrase(order.section.name)}. Исполнитель: {_end(_assignee_label(order))}"
    )
    data = None
    candidate = await suggest_free_worker(session, order)
    if candidate is not None:
        body += (
            f" Свободен: {candidate.short_name} ({candidate.specialty})."
            if candidate.specialty
            else f" Свободен: {_end(candidate.short_name)}"
        )
        data = {"reassign_to": candidate.id, "reassign_name": candidate.short_name}
    else:
        body += " Свободных исполнителей сейчас нет."
    await notify(
        session,
        employee_id=order.master_id,
        kind="order_escalation",
        title=f"Наряд №{order.number} не принят {waited}",
        body=body,
        order_id=order.id,
        urgent=order.priority == Priority.EMERGENCY,
        data=data,
    )
    order.escalated_at = now
    return Fired("escalation", order.number)


async def _remind(session: AsyncSession, order: Order, now: datetime) -> Fired | None:
    left = order.deadline_at - now
    if order.reminder_sent_at or left <= timedelta(0):
        return None
    if left > timedelta(minutes=settings.remind_before_min):
        return None
    for employee_id in await _recipients(session, order):
        await notify(
            session,
            employee_id=employee_id,
            kind="deadline_soon",
            title=f"Наряд №{order.number}: до срока {duration(math.ceil(left / MINUTE))}",
            body=f"Срок — {local_time(order.deadline_at)}. {order.equipment.name}, "
            f"{section_phrase(order.section.name)}. Статус: {_status_since(order)}.",
            order_id=order.id,
        )
    order.reminder_sent_at = now
    return Fired("reminder", order.number)


async def _overdue(session: AsyncSession, order: Order, now: datetime) -> list[Fired]:
    if now < order.deadline_at:
        return []
    fired: list[Fired] = []
    every = timedelta(minutes=settings.repeat_min)
    if order.overdue_notified_at is None or now - order.overdue_notified_at >= every:
        text = await overdue_text(session, order, now)
        title = f"Наряд №{order.number} просрочен"
        for employee_id in {*await _recipients(session, order), order.master_id}:
            await notify(
                session,
                employee_id=employee_id,
                kind="order_overdue",
                title=title,
                body=text,
                order_id=order.id,
            )
        order.overdue_notified_at = now
        fired.append(Fired("overdue", order.number))

    if order.boss_notified_at is None and now - order.deadline_at >= timedelta(
        minutes=settings.boss_overdue_min
    ):
        text = await overdue_text(session, order, now)
        bosses = await session.scalars(
            select(Employee.id).where(Employee.role == Role.BOSS, Employee.is_active.is_(True))
        )
        for boss_id in bosses:
            await notify(
                session,
                employee_id=boss_id,
                kind="order_overdue_boss",
                title=f"Длительная просрочка: наряд №{order.number}",
                body=f"{text} Мастер: {order.master.short_name}.",
                order_id=order.id,
            )
        order.boss_notified_at = now
        fired.append(Fired("boss", order.number))
    return fired


async def check_deadlines(
    session: AsyncSession, now: datetime | None = None, order_ids: list[int] | None = None
) -> list[Fired]:
    """Проверить все наряды до «Исполнено» (и на доработке). Commit — у вызывающего."""
    now = now or utcnow()
    stmt = (
        select(Order)
        .where(Order.status.in_(DEADLINE_TRACKED_STATUSES))
        .options(
            selectinload(Order.equipment),
            selectinload(Order.section),
            selectinload(Order.assignee),
            selectinload(Order.master),
            selectinload(Order.brigade),
        )
        .order_by(Order.deadline_at)
    )
    if order_ids is not None:
        stmt = stmt.where(Order.id.in_(order_ids))

    fired: list[Fired] = []
    for order in list(await session.scalars(stmt)):
        for rule in (_alarm, _escalate, _remind):
            if result := await rule(session, order, now):
                fired.append(result)
        fired.extend(await _overdue(session, order, now))
    return fired
