from decimal import Decimal

from pydantic import BaseModel, Field

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


class NormMaterialOut(BaseModel):
    material_id: int
    name: str
    unit: str
    quantity: Decimal


class FaultCodeOut(ORMModel, FaultCodeIn):
    id: int
    norm_hours: Decimal | None = None
    norm_materials: list[NormMaterialOut] = []


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


class ImportResult(BaseModel):
    created: int
    updated: int
    errors: list[str]
