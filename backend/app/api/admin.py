"""Справочники для администратора: CRUD и импорт из CSV (задел под выгрузки из 1С / ТОиР)."""

import csv
import io
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_role
from app.errors import Conflict, Invalid, NotFound
from app.models import Base, Brigade, Employee, Equipment, FaultCode, Material, Section
from app.models.enums import Role
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
    MaterialIn,
    MaterialOut,
    SectionIn,
    SectionOut,
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


def _out(kind: RefKind, obj: Any) -> dict[str, Any]:
    return kind.schema_out.model_validate(obj).model_dump(mode="json")


async def _commit(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict(
            "Запись конфликтует с существующей: такое название, номер или логин уже есть, "
            "либо запись используется в нарядах."
        ) from exc


@router.get("/{kind_name}", summary="Список записей справочника")
async def list_items(
    kind_name: str, session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    kind = _kind(kind_name)
    rows = await session.scalars(select(kind.model).order_by(getattr(kind.model, kind.order_by)))
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
    _apply(obj, data)
    session.add(obj)
    await _commit(session)
    return _out(kind, obj)


@router.patch("/{kind_name}/{item_id}", summary="Изменить запись")
async def update_item(
    kind_name: str,
    item_id: int,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    kind = _kind(kind_name)
    obj = await session.get(kind.model, item_id)
    if obj is None:
        raise NotFound("Запись не найдена.")
    current = _out(kind, obj)
    data = _validate(kind, {**current, **body})
    _apply(obj, {k: v for k, v in data.items() if k in body})
    await _commit(session)
    return _out(kind, obj)


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
            if existing is not None:
                merged = {**_out(kind, existing), **clean}
                data = _validate(kind, merged)
                _apply(existing, {k: v for k, v in data.items() if k in clean})
                updated += 1
            else:
                data = _validate(kind, clean)
                obj = kind.model()
                _apply(obj, data)
                session.add(obj)
                created += 1
            await session.flush()
        except (Invalid, IntegrityError) as exc:
            await session.rollback()
            message = exc.message if isinstance(exc, Invalid) else "дубликат или неверная ссылка"
            errors.append(f"Строка {line_no}: {message}")
            return ImportResult(created=0, updated=0, errors=errors)
    await _commit(session)
    return ImportResult(created=created, updated=updated, errors=errors)
