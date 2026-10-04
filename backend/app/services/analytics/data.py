"""Наряды за период одной таблицей pandas — общий вход для всех детекторов."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import MaterialWriteoff, Order, TimeNorm, TimeNormMaterial
from app.models.base import utcnow
from app.models.enums import OrderStatus, OrderType
from app.models.reference import FaultCode
from app.services.quality import had_rework, repeat_breakdowns

DONE_STATUSES = {OrderStatus.DONE, OrderStatus.AI_REVIEW, OrderStatus.CLOSED}


@dataclass(frozen=True)
class Scope:
    """Период и фильтры, по которым строится аналитика."""

    days: int = 90
    section_id: int | None = None
    equipment_id: int | None = None
    now: datetime | None = None

    @property
    def end(self) -> datetime:
        return self.now or utcnow()

    @property
    def start(self) -> datetime:
        return self.end - timedelta(days=self.days)


@dataclass(frozen=True)
class Frames:
    orders: pd.DataFrame
    materials: pd.DataFrame  # списания с нормой: order_id, worker, category, ratio


def _night(dt: datetime) -> bool:
    hour = dt.astimezone(settings.tz).hour
    return hour >= settings.night_shift_start_hour or hour < settings.day_shift_start_hour


async def load(session: AsyncSession, scope: Scope) -> Frames:
    stmt = (
        select(Order)
        .where(Order.created_at >= scope.start, Order.created_at <= scope.end)
        .options(
            selectinload(Order.equipment),
            selectinload(Order.section),
            selectinload(Order.assignee),
            selectinload(Order.brigade),
            selectinload(Order.fault_code)
            .selectinload(FaultCode.norm)
            .selectinload(TimeNorm.materials)
            .selectinload(TimeNormMaterial.material),
            selectinload(Order.writeoffs).selectinload(MaterialWriteoff.material),
            selectinload(Order.events),
        )
    )
    if scope.section_id is not None:
        stmt = stmt.where(Order.section_id == scope.section_id)
    if scope.equipment_id is not None:
        stmt = stmt.where(Order.equipment_id == scope.equipment_id)
    orders = list(await session.scalars(stmt))
    unplanned = [o for o in orders if o.type == OrderType.UNPLANNED]
    repeats = repeat_breakdowns([o for o in orders if o.status in DONE_STATUSES], unplanned)

    rows = []
    lines = []
    for o in orders:
        code = o.fault_code.code if o.fault_code else None
        rows.append(
            {
                "id": o.id,
                "number": o.number,
                "unplanned": o.type == OrderType.UNPLANNED,
                "status": o.status.value,
                "done": o.status in DONE_STATUSES,
                "created_at": o.created_at,
                "done_at": o.done_at,
                "night": _night(o.created_at),
                "equipment_id": o.equipment_id,
                "equipment": o.equipment.name,
                "equipment_type": o.equipment.type,
                "criticality": o.equipment.criticality.value,
                "section_id": o.section_id,
                "section": o.section.name,
                "code": code,
                "code_group": code[:1] if code else None,
                "code_name": o.fault_code.name if o.fault_code else None,
                "assignee_id": o.assignee_id,
                "assignee": o.assignee.short_name if o.assignee else None,
                "brigade_id": o.brigade_id,
                "brigade": o.brigade.name if o.brigade else None,
                "downtime": o.downtime_minutes or 0,
                "rework": had_rework(o),
                "repeat": o.id in repeats,
                "planned": o.type == OrderType.PLANNED,
            }
        )
        norm = (
            {line.material_id: line.quantity for line in o.fault_code.norm.materials}
            if o.fault_code and o.fault_code.norm
            else {}
        )
        for w in o.writeoffs:
            if w.material_id in norm and norm[w.material_id] > 0 and o.assignee is not None:
                lines.append(
                    {
                        "order_id": o.id,
                        "worker_id": o.assignee_id,
                        "worker": o.assignee.short_name,
                        "category": w.material.category,
                        "material": w.material.name,
                        "ratio": float(w.quantity / norm[w.material_id]),
                    }
                )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True)
        frame["done_at"] = pd.to_datetime(frame["done_at"], utc=True)
    return Frames(frame, pd.DataFrame(lines))
