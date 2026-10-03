from pydantic import BaseModel, ConfigDict

from app.models.enums import Criticality


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RefShort(ORMModel):
    id: int
    name: str


class EquipmentShort(ORMModel):
    id: int
    name: str
    inv_number: str
    section_id: int
    type: str
    criticality: Criticality


class PersonShort(ORMModel):
    id: int
    full_name: str
    short_name: str
    specialty: str | None = None


class FaultCodeShort(ORMModel):
    id: int
    code: str
    name: str
