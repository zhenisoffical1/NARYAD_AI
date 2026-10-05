"""Справочники для администратора: CRUD и импорт из CSV (задел под выгрузки из 1С / ТОиР)."""

import csv
import io
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy import Integer, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import get_session
from app.deps import require_role
from app.errors import Conflict, Invalid, NotFound
from app.models import (
    Base,
    Brigade,
    Employee,
    Equipment,
    FaultCode,
    LlmCall,
    Material,
    Order,
    Section,
    TimeNorm,
    TimeNormMaterial,
)
from app.models.base import utcnow
from app.models.enums import ACTIVE_STATUSES, Role
from app.schemas.reference import (
    BrigadeIn,
    BrigadeOut,
    EmployeeAdminOut,
    EmployeeIn,
    EquipmentIn,
    EquipmentOut,
    FaultCodeIn,
    FaultCodeOut,
    ImportResult,
    LlmCallOut,
    MaterialIn,
    MaterialOut,
    SectionIn,
    SectionOut,
    SystemStatus,
    fault_code_out,
)
from app.security import hash_pin

router = APIRouter(
    prefix="/admin", tags=["Администрирование"], dependencies=[Depends(require_role(Role.ADMIN))]
)


@dataclass(frozen=True, slots=True)
class RefKind:
    model: type[Base]
    schema_in: type[BaseModel]
    schema_out: type[BaseModel]
    natural_key: str  # по нему импорт находит существующую запись
    order_by: str


KINDS: dict[str, RefKind] = {
    "sections": RefKind(Section, SectionIn, SectionOut, "name", "name"),
    "equipment": RefKind(Equipment, EquipmentIn, EquipmentOut, "inv_number", "name"),
    "brigades": RefKind(Brigade, BrigadeIn, BrigadeOut, "name", "name"),
    "fault-codes": RefKind(FaultCode, FaultCodeIn, FaultCodeOut, "code", "code"),
    "materials": RefKind(Material, MaterialIn, MaterialOut, "name", "name"),
    "employees": RefKind(Employee, EmployeeIn, EmployeeAdminOut, "login", "full_name"),
}


def _kind(name: str) -> RefKind:
    kind = KINDS.get(name)
    if kind is None:
        raise NotFound(f"Справочника «{name}» нет. Доступны: {', '.join(KINDS)}.")
    return kind


def _apply(obj: Any, data: dict[str, Any]) -> None:
    pin = data.pop("pin", None)
    for key, value in data.items():
        setattr(obj, key, value)
    if pin:
        obj.pin_hash = hash_pin(pin)


NORM = (
    selectinload(FaultCode.norm)
    .selectinload(TimeNorm.materials)
    .selectinload(TimeNormMaterial.material)
)


def _out(kind: RefKind, obj: Any) -> dict[str, Any]:
    if kind.model is FaultCode:
        return fault_code_out(obj).model_dump(mode="json")
    return kind.schema_out.model_validate(obj).model_dump(mode="json")


async def _get(session: AsyncSession, kind: RefKind, item_id: int) -> Any:
    """Запись по id; у шифра — сразу с нормативом (ленивая загрузка в async недоступна)."""
    stmt = select(kind.model).where(kind.model.id == item_id)  # type: ignore[attr-defined]
    if kind.model is FaultCode:
        stmt = stmt.options(NORM).execution_options(populate_existing=True)
    return await session.scalar(stmt)


async def _set_norm(session: AsyncSession, code: Any, data: dict[str, Any]) -> None:
    """Норматив времени шифра живёт в time_norms: обновляем или создаём."""
    hours = data.pop("norm_hours", None)
    if hours is None:
        return
    if code.id is not None:
        loaded = await _get(session, KINDS["fault-codes"], code.id)
        if loaded is not None and loaded.norm is not None:
            loaded.norm.norm_hours = hours
            return
    session.add(TimeNorm(fault_code=code, norm_hours=hours))


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict(
            "Запись конфликтует с существующей: такое название, номер или логин уже есть, "
            "либо запись используется в нарядах."
        ) from exc


@router.get("/system", response_model=SystemStatus, summary="Состояние системы")
async def system_status(session: AsyncSession = Depends(get_session)) -> SystemStatus:
    since = utcnow() - timedelta(hours=24)
    calls_24h = (
        await session.execute(
            select(
                func.count(), func.avg(LlmCall.latency_ms), func.sum(func.cast(LlmCall.ok, Integer))
            ).where(LlmCall.created_at >= since)
        )
    ).one()
    total, avg_latency, ok_count = calls_24h
    recent = await session.scalars(select(LlmCall).order_by(LlmCall.created_at.desc()).limit(12))

    async def count(stmt: Any) -> int:
        return int(await session.scalar(stmt) or 0)

    return SystemStatus(
        llm_mode=settings.llm_backend,
        llm_model=settings.active_model(),
        llm_fast_model=settings.active_model(fast=True),
        telegram=bool(settings.telegram_bot_token),
        telegram_bot=settings.telegram_bot_username,
        demo_mode=settings.demo_mode,
        employees_active=await count(
            select(func.count()).select_from(Employee).where(Employee.is_active)
        ),
        employees_telegram=await count(
            select(func.count()).select_from(Employee).where(Employee.telegram_chat_id.is_not(None))
        ),
        equipment=await count(select(func.count()).select_from(Equipment)),
        orders_total=await count(select(func.count()).select_from(Order)),
        orders_active=await count(
            select(func.count()).select_from(Order).where(Order.status.in_(ACTIVE_STATUSES))
        ),
        llm_calls_24h=int(total or 0),
        llm_ok_share=round(int(ok_count or 0) / total, 3) if total else None,
        llm_avg_latency_ms=round(avg_latency) if avg_latency is not None else None,
        llm_recent=[LlmCallOut.model_validate(c) for c in recent],
    )


@router.get("/{kind_name}", summary="Список записей справочника")
async def list_items(
    kind_name: str, session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    kind = _kind(kind_name)
    stmt = select(kind.model).order_by(getattr(kind.model, kind.order_by))
    if kind.model is FaultCode:
        stmt = stmt.options(NORM)
    rows = await session.scalars(stmt)
    return [_out(kind, r) for r in rows]


@router.post("/{kind_name}", status_code=201, summary="Добавить запись")
async def create_item(
    kind_name: str, body: dict[str, Any], session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    kind = _kind(kind_name)
    data = _validate(kind, body)
    if kind.model is Employee and not data.get("pin"):
        raise Invalid("Задайте сотруднику ПИН из 4 цифр.")
    obj = kind.model()
    norm = {"norm_hours": data.pop("norm_hours", None)} if kind.model is FaultCode else {}
    _apply(obj, data)
    session.add(obj)
    await _set_norm(session, obj, norm)
    await _commit(session)
    return _out(kind, await _get(session, kind, obj.id))  # type: ignore[attr-defined]


@router.patch("/{kind_name}/{item_id}", summary="Изменить запись")
async def update_item(
    kind_name: str,
    item_id: int,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    kind = _kind(kind_name)
    obj = await _get(session, kind, item_id)
    if obj is None:
        raise NotFound("Запись не найдена.")
    current = _out(kind, obj)
    data = _validate(kind, {**current, **body})
    changed = {k: v for k, v in data.items() if k in body}
    if kind.model is FaultCode:
        await _set_norm(session, obj, changed)
    _apply(obj, changed)
    await _commit(session)
    return _out(kind, await _get(session, kind, item_id))


@router.delete("/{kind_name}/{item_id}", status_code=204, summary="Удалить запись")
async def delete_item(
    kind_name: str, item_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    kind = _kind(kind_name)
    obj = await session.get(kind.model, item_id)
    if obj is None:
        raise NotFound("Запись не найдена.")
    await session.delete(obj)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        hint = " Отключите сотрудника вместо удаления." if kind.model is Employee else ""
        raise Conflict("Нельзя удалить: запись используется в нарядах." + hint) from exc


def _validate(kind: RefKind, raw: dict[str, Any]) -> dict[str, Any]:
    try:
        return kind.schema_in.model_validate(raw).model_dump()
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        raise Invalid(f"Проверьте поля: {problems}") from exc


async def _resolve_names(session: AsyncSession, kind: RefKind, row: dict[str, Any]) -> None:
    """В CSV удобнее писать названия, а не id: «section» → section_id, «brigade» → brigade_id."""
    if kind.model is Equipment and "section_id" not in row and row.get("section"):
        section = await session.scalar(select(Section).where(Section.name == row["section"]))
        if section is None:
            raise Invalid(f"участок «{row['section']}» не найден")
        row["section_id"] = section.id
    if kind.model is Employee and "brigade_id" not in row and row.get("brigade"):
        brigade = await session.scalar(select(Brigade).where(Brigade.name == row["brigade"]))
        if brigade is None:
            raise Invalid(f"бригада «{row['brigade']}» не найдена")
        row["brigade_id"] = brigade.id
    row.pop("section", None)
    row.pop("brigade", None)


@router.post(
    "/{kind_name}/import",
    response_model=ImportResult,
    summary="Импорт из CSV (UTF-8, разделитель «;» или «,»). Существующие записи обновляются.",
)
async def import_csv(
    kind_name: str,
    file: UploadFile = File(),
    session: AsyncSession = Depends(get_session),
) -> ImportResult:
    kind = _kind(kind_name)
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")  # выгрузки из 1С часто в Windows-1251
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)

    created = updated = 0
    errors: list[str] = []
    key_column = getattr(kind.model, kind.natural_key)
    for line_no, row in enumerate(reader, start=2):
        clean = {k.strip(): (v.strip() if v else None) for k, v in row.items() if k}
        clean = {k: v for k, v in clean.items() if v not in (None, "")}
        try:
            await _resolve_names(session, kind, clean)
            existing = await session.scalar(
                select(kind.model).where(key_column == clean.get(kind.natural_key))
            )
            if existing is not None and kind.model is FaultCode:
                existing = await _get(session, kind, existing.id)  # type: ignore[attr-defined]
            if existing is not None:
                merged = {**_out(kind, existing), **clean}
                data = _validate(kind, merged)
                changed = {k: v for k, v in data.items() if k in clean}
                if kind.model is FaultCode:
                    await _set_norm(session, existing, changed)
                _apply(existing, changed)
                updated += 1
            else:
                data = _validate(kind, clean)
                obj = kind.model()
                norm = (
                    {"norm_hours": data.pop("norm_hours", None)} if kind.model is FaultCode else {}
                )
                _apply(obj, data)
                session.add(obj)
                await _set_norm(session, obj, norm)
                created += 1
            await session.flush()
        except (Invalid, IntegrityError) as exc:
            await session.rollback()
            message = exc.message if isinstance(exc, Invalid) else "дубликат или неверная ссылка"
            errors.append(f"Строка {line_no}: {message}")
            return ImportResult(created=0, updated=0, errors=errors)
    await _commit(session)
    return ImportResult(created=created, updated=updated, errors=errors)
