"""Справочники в БД и их удобное представление для генератора."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Base,
    Brigade,
    Employee,
    Equipment,
    FaultCode,
    Material,
    Section,
    TimeNorm,
    TimeNormMaterial,
)
from app.models.enums import Role, Shift
from app.security import hash_pin
from seed.reference_data import (
    BRIGADES,
    EQUIPMENT,
    FAULTS,
    MATERIALS,
    PEOPLE,
    SECTIONS,
    EquipmentSpec,
    FaultSpec,
)


@dataclass
class World:
    sections: dict[str, Section]
    equipment: dict[str, Equipment]  # по инвентарному номеру
    equipment_specs: dict[str, EquipmentSpec]
    faults: dict[str, FaultCode]  # по коду
    fault_specs: dict[str, FaultSpec]
    materials: dict[str, Material]  # по названию
    brigades: dict[str, Brigade]
    workers: list[Employee]
    masters: dict[Shift, Employee]
    people: dict[str, Employee]  # по логину

    def section_of(self, inv: str) -> Section:
        return self.sections[self.equipment_specs[inv].section]


async def wipe(session: AsyncSession) -> None:
    """Очистить все таблицы (в порядке зависимостей)."""
    for table in reversed(Base.metadata.sorted_tables):
        await session.execute(delete(table))
    await session.flush()


async def build_world(session: AsyncSession) -> World:
    sections = {name: Section(name=name, external_id=ext) for name, ext in SECTIONS}
    brigades = {name: Brigade(name=name, external_id=ext) for name, ext in BRIGADES}
    materials = {
        name: Material(name=name, unit=unit, category=cat, external_id=f"MAT-{i + 1:03d}")
        for i, (name, unit, cat) in enumerate(MATERIALS)
    }
    session.add_all([*sections.values(), *brigades.values(), *materials.values()])
    await session.flush()

    equipment = {
        spec.inv_number: Equipment(
            name=spec.name,
            inv_number=spec.inv_number,
            section_id=sections[spec.section].id,
            type=spec.type,
            criticality=spec.criticality,
            qr_code=f"NA-{spec.inv_number}",
            external_id=f"EQ-{i + 1:03d}",
        )
        for i, spec in enumerate(EQUIPMENT)
    }
    faults = {
        spec.code: FaultCode(
            code=spec.code, category=spec.code[0], name=spec.name, external_id=f"FC-{spec.code}"
        )
        for spec in FAULTS
    }
    session.add_all([*equipment.values(), *faults.values()])
    await session.flush()

    for spec in FAULTS:
        norm = TimeNorm(
            fault_code_id=faults[spec.code].id, norm_hours=Decimal(str(spec.norm_hours))
        )
        session.add(norm)
        await session.flush()
        for name, qty in spec.materials:
            session.add(
                TimeNormMaterial(
                    time_norm_id=norm.id,
                    material_id=materials[name].id,
                    quantity=Decimal(str(qty)),
                )
            )

    # Хэш ПИН считаем один раз на значение: PBKDF2 медленный намеренно
    pin_hashes = {pin: hash_pin(pin) for pin in {p.pin for p in PEOPLE}}
    people = {
        p.login: Employee(
            login=p.login,
            full_name=p.full_name,
            role=p.role,
            specialty=p.specialty,
            grade=p.grade,
            brigade_id=brigades[p.brigade].id if p.brigade else None,
            shift=p.shift,
            on_shift=False,
            pin_hash=pin_hashes[p.pin],
            external_id=f"TAB-{i + 101}",
        )
        for i, p in enumerate(PEOPLE)
    }
    session.add_all(people.values())
    await session.flush()

    workers = [e for e in people.values() if e.role == Role.WORKER]
    masters = {e.shift: e for e in people.values() if e.role == Role.MASTER and e.shift}
    return World(
        sections=sections,
        equipment=equipment,
        equipment_specs={s.inv_number: s for s in EQUIPMENT},
        faults=faults,
        fault_specs={s.code: s for s in FAULTS},
        materials=materials,
        brigades=brigades,
        workers=workers,
        masters=masters,
        people=people,
    )
