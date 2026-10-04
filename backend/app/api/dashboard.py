"""Дашборд руководителя: состояние на сейчас и итоги периода на одном экране."""

from collections import defaultdict
from datetime import timedelta
from statistics import median
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.deps import require_role
from app.models import Order
from app.models.base import utcnow
from app.models.enums import DEADLINE_TRACKED_STATUSES, OrderStatus, OrderType, Role
from app.services.rating import compute_ratings

router = APIRouter(prefix="/dashboard", tags=["Руководитель"])

S = OrderStatus
DONE = {S.DONE, S.AI_REVIEW, S.CLOSED}


class Point(BaseModel):
    label: str
    value: float


class EquipmentRow(BaseModel):
    equipment_id: int
    name: str
    section: str
    unplanned: int
    downtime_hours: float


class WorkerRow(BaseModel):
    employee_id: int
    name: str
    score: float
    orders: int


class Dashboard(BaseModel):
    days: int
    in_work: int
    overdue_now: int
    issued: int
    done: int
    overdue_share: float  # доля исполненных с нарушением срока
    reaction_minutes: float | None  # медиана: выдан → принят
    completion_hours: float | None  # медиана: начат → исполнен
    downtime_hours: float
    unplanned_share: float
    trend: list[Point]  # внеплановые по дням
    top_equipment: list[EquipmentRow]
    best_workers: list[WorkerRow]


@router.get("", response_model=Dashboard, summary="Показатели для руководителя")
async def dashboard(
    days: int = Query(default=30, ge=1, le=365),
    section_id: int | None = None,
    _user: Any = Depends(require_role(Role.BOSS, Role.ADMIN, Role.MASTER)),
    session: AsyncSession = Depends(get_session),
) -> Dashboard:
    now = utcnow()
    start = now - timedelta(days=days)

    active_stmt = select(Order).where(Order.status.in_(DEADLINE_TRACKED_STATUSES))
    period_stmt = (
        select(Order)
        .where(Order.created_at >= start)
        .options(selectinload(Order.equipment), selectinload(Order.section))
    )
    if section_id is not None:
        active_stmt = active_stmt.where(Order.section_id == section_id)
        period_stmt = period_stmt.where(Order.section_id == section_id)
    active = list(await session.scalars(active_stmt))
    orders = list(await session.scalars(period_stmt))

    done = [o for o in orders if o.status in DONE and o.done_at]
    late = [o for o in done if o.done_at and o.done_at > o.deadline_at]
    reactions = [
        (o.accepted_at - o.issued_at).total_seconds() / 60
        for o in orders
        if o.accepted_at and o.issued_at and o.accepted_at >= o.issued_at
    ]
    completions = [
        (o.done_at - o.started_at).total_seconds() / 3600
        for o in done
        if o.done_at and o.started_at
    ]
    unplanned = [o for o in orders if o.type == OrderType.UNPLANNED]

    by_day: dict[str, int] = defaultdict(int)
    for o in unplanned:
        by_day[o.created_at.strftime("%Y-%m-%d")] += 1
    trend = [
        Point(
            label=(start + timedelta(days=i + 1)).strftime("%d.%m"),
            value=by_day.get((start + timedelta(days=i + 1)).strftime("%Y-%m-%d"), 0),
        )
        for i in range(days)
    ]

    per_equipment: dict[int, EquipmentRow] = {}
    for o in unplanned:
        row = per_equipment.setdefault(
            o.equipment_id,
            EquipmentRow(
                equipment_id=o.equipment_id,
                name=o.equipment.name,
                section=o.section.name,
                unplanned=0,
                downtime_hours=0,
            ),
        )
        row.unplanned += 1
        row.downtime_hours = round(row.downtime_hours + (o.downtime_minutes or 0) / 60, 1)
    top = sorted(per_equipment.values(), key=lambda r: (-r.unplanned, -r.downtime_hours))[:5]

    ratings = await compute_ratings(session, days=max(days, 7), now=now)
    best = [
        WorkerRow(
            employee_id=r.employee.id, name=r.employee.short_name, score=r.score, orders=r.orders
        )
        for r in ratings.workers
        if r.score is not None
    ][:5]

    return Dashboard(
        days=days,
        in_work=sum(1 for o in active if o.status in (S.ACCEPTED, S.IN_PROGRESS, S.REWORK)),
        overdue_now=sum(1 for o in active if o.deadline_at < now),
        issued=len(orders),
        done=len(done),
        overdue_share=round(len(late) / len(done), 3) if done else 0,
        reaction_minutes=round(median(reactions), 1) if reactions else None,
        completion_hours=round(median(completions), 2) if completions else None,
        downtime_hours=round(sum(o.downtime_minutes or 0 for o in orders) / 60, 1),
        unplanned_share=round(len(unplanned) / len(orders), 3) if orders else 0,
        trend=trend,
        top_equipment=top,
        best_workers=best,
    )
