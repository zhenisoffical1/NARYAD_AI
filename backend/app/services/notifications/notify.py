"""Уведомление сотруднику: запись в ленту PWA + живое событие. Telegram подключается сюда же."""

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
) -> Notification:
    note = Notification(
        employee_id=employee_id,
        order_id=order_id,
        kind=kind,
        title=title,
        body=body,
        created_at=utcnow(),
    )
    session.add(note)
    await session.flush()
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
