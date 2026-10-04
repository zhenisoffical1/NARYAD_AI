"""Уведомление сотруднику: запись в ленту PWA + живое событие.

Telegram-бот забирает неотправленные записи сам (`telegram_sent_at IS NULL`) — поэтому
уведомление из бэкенда, планировщика или бота доходит одинаково и не теряется, если бот
перезапускался.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification
from app.models.base import utcnow
from app.services.notifications.live import LiveEvent, queue_event


async def notify(
    session: AsyncSession,
    *,
    employee_id: int,
    kind: str,
    title: str,
    body: str,
    order_id: int | None = None,
    urgent: bool = False,
    data: dict[str, Any] | None = None,
    feed: bool = True,
) -> Notification:
    """`feed=False` — только Telegram (повтор аварийного), в ленте PWA не показывается."""
    note = Notification(
        employee_id=employee_id,
        order_id=order_id,
        kind=kind,
        title=title,
        body=body,
        urgent=urgent,
        data=data,
        feed=feed,
        created_at=utcnow(),
    )
    session.add(note)
    await session.flush()
    if feed:
        queue_event(
            session,
            LiveEvent(
                type="notification.created",
                payload={
                    "id": note.id,
                    "kind": kind,
                    "title": title,
                    "body": body,
                    "order_id": order_id,
                    "urgent": urgent,
                },
                user_ids=frozenset({employee_id}),
            ),
        )
    return note
