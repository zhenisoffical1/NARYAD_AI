"""Статусы людей смены и счётчики смены для панели мастера."""

from collections import defaultdict
from datetime import datetime

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, Order
from app.models.base import utcnow
from app.models.enums import (
    DEADLINE_TRACKED_STATUSES,
    PRIORITY_RANK,
    OrderStatus,
    Role,
)
from app.schemas.common import PersonShort
from app.schemas.orders import OrderRef, PersonState, PersonStatus, ShiftSummary
from app.services.shifts import shift_bounds

S = OrderStatus

# Чем занят исполнитель: «в работе» — то, что он уже делает; «очередь» — ждёт его
WORK_STATUSES = (S.IN_PROGRESS, S.REWORK, S.ACCEPTED)
QUEUE_STATUSES = (S.ISSUED, S.QUEUED, S.PAUSED)

_STATE_ORDER: dict[PersonState, int] = {"free": 0, "queue": 1, "busy": 2, "off_shift": 3}


def person_state(
    on_shift: bool, work: list[Order], queue: list[Order]
) -> tuple[PersonState, Order | None]:
    if work:
        current = min(
            work, key=lambda o: (WORK_STATUSES.index(o.status), PRIORITY_RANK[o.priority])
        )
        return "busy", current
    if not on_shift:
        return "off_shift", None
    if queue:
        return "queue", None
    return "free", None


async def shift_people(session: AsyncSession) -> list[PersonStatus]:
    workers = list(
        await session.scalars(
            select(Employee).where(Employee.role == Role.WORKER, Employee.is_active.is_(True))
        )
    )
    orders = await session.scalars(
        select(Order).where(
            Order.assignee_id.in_([w.id for w in workers]),
            Order.status.in_(WORK_STATUSES + QUEUE_STATUSES),
        )
    )
    work: dict[int, list[Order]] = defaultdict(list)
    queue: dict[int, list[Order]] = defaultdict(list)
    for order in orders:
        assert order.assignee_id is not None
        (work if order.status in WORK_STATUSES else queue)[order.assignee_id].append(order)

    result = []
    for worker in workers:
        state, current = person_state(worker.on_shift, work[worker.id], queue[worker.id])
        result.append(
            PersonStatus(
                employee=PersonShort.model_validate(worker),
                brigade_id=worker.brigade_id,
                on_shift=worker.on_shift,
                state=state,
                current_order=OrderRef(id=current.id, number=current.number) if current else None,
                queue_count=len(queue[worker.id]),
            )
        )
    result.sort(key=lambda p: (_STATE_ORDER[p.state], p.employee.full_name))
    return result


async def shift_summary(session: AsyncSession, now: datetime | None = None) -> ShiftSummary:
    now = now or utcnow()
    _, start, end = shift_bounds(now)

    async def count(*conditions: ColumnElement[bool]) -> int:
        return int(
            await session.scalar(select(func.count()).select_from(Order).where(*conditions)) or 0
        )

    in_shift = (start, end)
    tracked = Order.status.in_(DEADLINE_TRACKED_STATUSES)
    equipment_down = await session.scalar(
        select(func.count(func.distinct(Order.equipment_id))).where(
            tracked, Order.equipment_stopped.is_(True)
        )
    )
    return ShiftSummary(
        shift_start=start,
        shift_end=end,
        issued=await count(Order.issued_at >= in_shift[0], Order.issued_at < in_shift[1]),
        done=await count(Order.done_at >= in_shift[0], Order.done_at < in_shift[1]),
        rejected=await count(Order.rejected_at >= in_shift[0], Order.rejected_at < in_shift[1]),
        overdue=await count(tracked, Order.deadline_at < now),
        in_progress=await count(Order.status == S.IN_PROGRESS),
        equipment_down=int(equipment_down or 0),
    )
