"""Справочники для всех ролей + история оборудования, статусы людей, счётчики смены."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.deps import get_current_user, require_role
from app.errors import NotFound
from app.models import (
    Brigade,
    Employee,
    Equipment,
    FaultCode,
    Material,
    Order,
    Section,
    TimeNorm,
    TimeNormMaterial,
)
from app.models.base import utcnow
from app.models.enums import OrderType, Role
from app.schemas.common import EquipmentShort, RefShort
from app.schemas.orders import EquipmentHistory, PersonStatus, ShiftSummary
from app.schemas.reference import (
    BrigadeOut,
    EquipmentOut,
    FaultCodeOut,
    MaterialOut,
    SectionOut,
    fault_code_out,
)
from app.services import orders as order_svc
from app.services.people import shift_people, shift_summary

router = APIRouter(tags=["Справочники"], dependencies=[Depends(get_current_user)])
staff_only = require_role(Role.MASTER, Role.BOSS, Role.ADMIN)


@router.get("/sections", response_model=list[SectionOut], summary="Участки")
async def sections(session: AsyncSession = Depends(get_session)) -> list[Section]:
    return list(await session.scalars(select(Section).order_by(Section.name)))


@router.get("/equipment", response_model=list[EquipmentOut], summary="Оборудование")
async def equipment(
    section_id: int | None = None,
    q: str | None = Query(default=None, max_length=60),
    session: AsyncSession = Depends(get_session),
) -> list[Equipment]:
    stmt = select(Equipment).order_by(Equipment.name)
    if section_id is not None:
        stmt = stmt.where(Equipment.section_id == section_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Equipment.name.ilike(pattern), Equipment.inv_number.ilike(pattern)))
    return list(await session.scalars(stmt))


@router.get(
    "/equipment/recent",
    response_model=list[EquipmentOut],
    summary="Последнее оборудование, на которое мастер выдавал наряды",
)
async def recent_equipment(
    limit: int = Query(default=6, ge=1, le=20),
    user: Employee = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Equipment]:
    latest = (
        select(Order.equipment_id, func.max(Order.created_at).label("last"))
        .where(Order.master_id == user.id)
        .group_by(Order.equipment_id)
        .subquery()
    )
    stmt = (
        select(Equipment)
        .join(latest, latest.c.equipment_id == Equipment.id)
        .order_by(latest.c.last.desc())
        .limit(limit)
    )
    return list(await session.scalars(stmt))


@router.get("/equipment/by-qr/{code}", response_model=EquipmentOut, summary="Оборудование по QR")
async def equipment_by_qr(code: str, session: AsyncSession = Depends(get_session)) -> Equipment:
    item = await session.scalar(
        select(Equipment).where(or_(Equipment.qr_code == code, Equipment.inv_number == code))
    )
    if item is None:
        raise NotFound("QR-код не найден в справочнике оборудования.")
    return item


@router.get(
    "/equipment/{equipment_id}/history",
    response_model=EquipmentHistory,
    summary="История нарядов, ремонтов и простоев оборудования",
)
async def equipment_history(
    equipment_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    user: Employee = Depends(staff_only),
    session: AsyncSession = Depends(get_session),
) -> EquipmentHistory:
    item = await session.scalar(
        select(Equipment)
        .where(Equipment.id == equipment_id)
        .options(selectinload(Equipment.section))
    )
    if item is None:
        raise NotFound("Оборудование не найдено.")
    totals = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(Order.type == OrderType.UNPLANNED),
                func.coalesce(func.sum(Order.downtime_minutes), 0),
            ).where(Order.equipment_id == equipment_id)
        )
    ).one()
    orders = await order_svc.list_orders(
        session, user, order_svc.OrderFilters(equipment_id=equipment_id, limit=limit)
    )
    return EquipmentHistory(
        equipment=EquipmentShort.model_validate(item),
        section=RefShort.model_validate(item.section),
        orders_total=totals[0],
        unplanned_total=totals[1],
        downtime_minutes_total=int(totals[2] or 0),
        orders=orders,
    )


@router.get("/brigades", response_model=list[BrigadeOut], summary="Бригады")
async def brigades(session: AsyncSession = Depends(get_session)) -> list[Brigade]:
    return list(await session.scalars(select(Brigade).order_by(Brigade.name)))


@router.get(
    "/fault-codes",
    response_model=list[FaultCodeOut],
    summary="Шифры неисправностей с нормативами времени и материалов",
)
async def fault_codes(session: AsyncSession = Depends(get_session)) -> list[FaultCodeOut]:
    codes = await session.scalars(
        select(FaultCode)
        .order_by(FaultCode.code)
        .options(
            selectinload(FaultCode.norm)
            .selectinload(TimeNorm.materials)
            .selectinload(TimeNormMaterial.material)
        )
    )
    return [fault_code_out(code) for code in codes]


@router.get("/materials", response_model=list[MaterialOut], summary="Материалы и запчасти")
async def materials(
    q: str | None = Query(default=None, max_length=60),
    session: AsyncSession = Depends(get_session),
) -> list[Material]:
    stmt = select(Material).order_by(Material.name)
    if q:
        stmt = stmt.where(Material.name.ilike(f"%{q.strip()}%"))
    return list(await session.scalars(stmt))


@router.get(
    "/people/shift",
    response_model=list[PersonStatus],
    summary="Исполнители: свободен / в работе №… / очередь N / не на смене",
)
async def people_on_shift(
    _user: Employee = Depends(staff_only), session: AsyncSession = Depends(get_session)
) -> list[PersonStatus]:
    return await shift_people(session)


@router.get("/shift/summary", response_model=ShiftSummary, summary="Счётчики текущей смены")
async def summary(
    _user: Employee = Depends(staff_only), session: AsyncSession = Depends(get_session)
) -> ShiftSummary:
    return await shift_summary(session, utcnow())
