"""Логика бота поверх общих сервисов: привязка и кнопки. Без aiogram — тестируется напрямую.

Действие из Telegram проходит тот же путь, что и из PWA: `perform_action` → state_machine →
журнал → живое событие. Поэтому статус у мастера меняется так же быстро.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Forbidden, Invalid
from app.models import Employee
from app.models.base import utcnow
from app.models.enums import STATUS_LABELS
from app.schemas.orders import ActionRequest, ReassignRequest
from app.services.notifications.live import commit_and_publish
from app.services.orders import load_order, local_time, perform_action, reassign_order
from app.services.state_machine import Action
from app.services.telegram_link import parse_token

ALLOWED_ACTIONS = frozenset({Action.ACCEPT, Action.QUEUE})

NOT_LINKED = (
    "Этот Telegram не привязан к НарядAI. Откройте приложение → «Профиль» → «Подключить Telegram»."
)


async def link_chat(session: AsyncSession, token: str, chat_id: int) -> str:
    employee_id = parse_token(token, utcnow())
    employee = await session.get(Employee, employee_id) if employee_id else None
    if employee is None or not employee.is_active:
        return "Ссылка устарела. Откройте приложение и нажмите «Подключить Telegram» ещё раз."
    # Один чат — один сотрудник: телефон мог перейти к другому человеку
    await session.execute(
        update(Employee).where(Employee.telegram_chat_id == chat_id).values(telegram_chat_id=None)
    )
    employee.telegram_chat_id = chat_id
    await session.commit()
    return (
        f"Готово, {employee.full_name}. Новые наряды, напоминания о сроках и просрочки "
        "будут приходить сюда. Отключить — /stop."
    )


async def unlink_chat(session: AsyncSession, chat_id: int) -> str:
    result = await session.execute(
        update(Employee).where(Employee.telegram_chat_id == chat_id).values(telegram_chat_id=None)
    )
    await session.commit()
    if not getattr(result, "rowcount", 0):
        return NOT_LINKED
    return "Уведомления в Telegram отключены. Наряды по-прежнему приходят в приложение."


async def employee_by_chat(session: AsyncSession, chat_id: int) -> Employee:
    employee = await session.scalar(
        select(Employee).where(Employee.telegram_chat_id == chat_id, Employee.is_active.is_(True))
    )
    if employee is None:
        raise Forbidden(NOT_LINKED)
    return employee


async def handle_callback(session: AsyncSession, chat_id: int, data: str) -> str:
    """Кнопка из сообщения → действие. Возвращает строку-итог для сообщения.

    Ошибки (наряд уже принят, переназначен и т. п.) — DomainError с понятным текстом.
    """
    user = await employee_by_chat(session, chat_id)
    try:
        kind, raw_order, raw_arg = data.split(":", 2)
        order_id = int(raw_order)
    except ValueError:
        raise Invalid("Кнопка устарела. Откройте наряд в приложении.") from None

    order = await load_order(session, order_id)
    if kind == "o":
        try:
            action = Action(raw_arg)
        except ValueError:
            raise Invalid("Кнопка устарела. Откройте наряд в приложении.") from None
        if action not in ALLOWED_ACTIONS:
            raise Invalid("Это действие выполняется в приложении.")
        await perform_action(session, order, action, user, ActionRequest())
    elif kind == "r":
        await reassign_order(
            session,
            order,
            user,
            ReassignRequest(assignee_id=int(raw_arg), comment="Переназначен из Telegram"),
        )
    else:
        raise Invalid("Кнопка устарела. Откройте наряд в приложении.")

    await commit_and_publish(session)
    status = STATUS_LABELS[order.status]
    assignee = await session.get(Employee, order.assignee_id) if order.assignee_id else None
    who = f" — {assignee.short_name}" if kind == "r" and assignee else ""
    return f"{status}{who} · {local_time(utcnow())}"
