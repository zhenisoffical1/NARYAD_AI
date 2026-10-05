from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, computed_field

from app.models.enums import Criticality, Role, Shift
from app.schemas.common import ORMModel


class SectionIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    external_id: str | None = Field(default=None, max_length=64)


class SectionOut(ORMModel, SectionIn):
    id: int


class EquipmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    inv_number: str = Field(min_length=1, max_length=32)
    section_id: int
    type: str = Field(min_length=2, max_length=80)
    criticality: Criticality = Criticality.B
    qr_code: str | None = Field(default=None, max_length=64)
    external_id: str | None = Field(default=None, max_length=64)


class EquipmentOut(ORMModel, EquipmentIn):
    id: int


class BrigadeIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    external_id: str | None = Field(default=None, max_length=64)


class BrigadeOut(ORMModel, BrigadeIn):
    id: int


class FaultCodeIn(BaseModel):
    code: str = Field(min_length=2, max_length=8)
    category: str = Field(min_length=1, max_length=2)
    name: str = Field(min_length=2, max_length=160)
    external_id: str | None = Field(default=None, max_length=64)
    # Норматив времени на работу по шифру (справочник нормативов, ТЗ 5.4)
    norm_hours: Decimal | None = Field(default=None, gt=0, le=1000)


class NormMaterialOut(BaseModel):
    material_id: int
    name: str
    unit: str
    quantity: Decimal


class FaultCodeOut(ORMModel, FaultCodeIn):
    id: int
    norm_hours: Decimal | None = None
    norm_materials: list[NormMaterialOut] = []


def fault_code_out(code: Any) -> FaultCodeOut:
    """Шифр с нормативом; норматив и его материалы должны быть загружены (selectinload)."""
    out = FaultCodeOut(
        id=code.id,
        code=code.code,
        category=code.category,
        name=code.name,
        external_id=code.external_id,
    )
    if code.norm:
        out.norm_hours = code.norm.norm_hours
        out.norm_materials = [
            NormMaterialOut(
                material_id=m.material_id,
                name=m.material.name,
                unit=m.material.unit,
                quantity=m.quantity,
            )
            for m in code.norm.materials
        ]
    return out


class MaterialIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    unit: str = Field(min_length=1, max_length=16)
    category: str | None = Field(default=None, max_length=40)
    external_id: str | None = Field(default=None, max_length=64)


class MaterialOut(ORMModel, MaterialIn):
    id: int


class EmployeeIn(BaseModel):
    login: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9._-]+$")
    full_name: str = Field(min_length=3, max_length=160)
    role: Role
    specialty: str | None = Field(default=None, max_length=60)
    grade: int | None = Field(default=None, ge=1, le=8)
    brigade_id: int | None = None
    shift: Shift | None = None
    on_shift: bool = False
    is_active: bool = True
    external_id: str | None = Field(default=None, max_length=64)
    pin: str | None = Field(default=None, pattern=r"^\d{4}$")


class EmployeeAdminOut(ORMModel):
    id: int
    login: str
    full_name: str
    role: Role
    specialty: str | None
    grade: int | None
    brigade_id: int | None
    shift: Shift | None
    on_shift: bool
    is_active: bool
    external_id: str | None
    telegram_chat_id: int | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def telegram_linked(self) -> bool:
        return self.telegram_chat_id is not None


class ImportResult(BaseModel):
    created: int
    updated: int
    errors: list[str]


class LlmCallOut(ORMModel):
    id: int
    purpose: str
    model: str
    latency_ms: int
    ok: bool
    error: str | None
    created_at: datetime


class SystemStatus(BaseModel):
    """Сводка для администратора: режимы, связь, объём данных, журнал вызовов модели."""

    llm_mode: str  # mock | anthropic | gemini
    llm_model: str
    llm_fast_model: str
    telegram: bool
    telegram_bot: str | None
    demo_mode: bool
    employees_active: int
    employees_telegram: int
    equipment: int
    orders_total: int
    orders_active: int
    llm_calls_24h: int
    llm_ok_share: float | None
    llm_avg_latency_ms: int | None
    llm_recent: list[LlmCallOut]
