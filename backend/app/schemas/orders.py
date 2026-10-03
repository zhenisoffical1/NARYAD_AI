from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import (
    AssessmentStatus,
    OrderStatus,
    OrderType,
    PhotoKind,
    Priority,
    Verdict,
)
from app.schemas.common import (
    EquipmentShort,
    FaultCodeShort,
    ORMModel,
    PersonShort,
    RefShort,
)


class OrderCreate(BaseModel):
    description: str = Field(min_length=3, max_length=4000)
    equipment_id: int
    priority: Priority
    assignee_id: int | None = None
    brigade_id: int | None = None
    type: OrderType | None = None  # по умолчанию из приоритета
    deadline_at: datetime | None = None
    norm_hours: Decimal | None = Field(default=None, gt=0, le=200)
    fault_code_id: int | None = None
    equipment_stopped: bool | None = None  # по умолчанию — да для аварийного
    comment: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _assignee_or_brigade(self) -> "OrderCreate":
        if self.assignee_id is None and self.brigade_id is None:
            raise ValueError("Выберите исполнителя или бригаду.")
        return self


class ActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)
    comment: str | None = Field(default=None, max_length=2000)


class MaterialLine(BaseModel):
    material_id: int
    quantity: Decimal = Field(gt=0, le=100000)


class CompleteRequest(BaseModel):
    works_done: str = Field(min_length=3, max_length=4000)
    fault_code_id: int
    materials: list[MaterialLine] = Field(default_factory=list, max_length=30)
    no_materials: bool = False
    comment: str | None = Field(default=None, max_length=2000)


class ReassignRequest(BaseModel):
    assignee_id: int
    comment: str | None = Field(default=None, max_length=2000)


class PriorityRequest(BaseModel):
    priority: Priority
    comment: str | None = Field(default=None, max_length=2000)


class OverrideRequest(BaseModel):
    score: int = Field(ge=0, le=100)
    comment: str = Field(min_length=3, max_length=2000)


class PhotoOut(ORMModel):
    id: int
    kind: PhotoKind
    url: str
    thumb_url: str
    taken_at: datetime | None
    uploaded_at: datetime
    author_id: int | None


class WriteoffOut(BaseModel):
    material_id: int
    name: str
    quantity: Decimal
    unit: str


class EventOut(ORMModel):
    id: int
    action: str
    from_status: OrderStatus | None
    to_status: OrderStatus | None
    actor: PersonShort | None
    reason: str | None
    comment: str | None
    data: dict[str, Any] | None
    created_at: datetime


class AssessmentOut(ORMModel):
    id: int
    status: AssessmentStatus
    mode: str
    verdict: Verdict | None
    score_0_100: int | None
    score_1_5: int | None
    confidence: float | None
    needs_master_review: bool
    explanation_worker: str | None
    explanation_master: str | None
    checks: list[Any] | None
    master_override_score: int | None
    master_comment: str | None
    final_score: int | None
    created_at: datetime
    finished_at: datetime | None


class OrderListItem(ORMModel):
    id: int
    number: int
    type: OrderType
    priority: Priority
    status: OrderStatus
    description: str
    equipment: EquipmentShort
    section: RefShort
    assignee: PersonShort | None
    master: PersonShort
    deadline_at: datetime
    created_at: datetime
    issued_at: datetime | None
    accepted_at: datetime | None
    started_at: datetime | None
    done_at: datetime | None
    closed_at: datetime | None
    updated_at: datetime
    equipment_stopped: bool
    is_overdue: bool = False
    overdue_minutes: int = 0
    ai_score: int | None = None
    ai_verdict: Verdict | None = None


class OrderDetail(OrderListItem):
    comment: str | None
    norm_hours: Decimal | None
    fault_code: FaultCodeShort | None
    works_done: str | None
    no_materials: bool
    closing_comment: str | None
    downtime_minutes: int | None
    events: list[EventOut]
    photos: list[PhotoOut]
    materials: list[WriteoffOut]
    assessment: AssessmentOut | None
    actions: list[str]


PersonState = Literal["off_shift", "free", "busy", "queue"]


class OrderRef(BaseModel):
    id: int
    number: int


class PersonStatus(BaseModel):
    employee: PersonShort
    brigade_id: int | None
    on_shift: bool
    state: PersonState
    current_order: OrderRef | None
    queue_count: int


class ShiftSummary(BaseModel):
    shift_start: datetime
    shift_end: datetime
    issued: int
    done: int
    overdue: int
    rejected: int
    equipment_down: int
    in_progress: int


class EquipmentHistory(BaseModel):
    equipment: EquipmentShort
    section: RefShort
    orders_total: int
    unplanned_total: int
    downtime_minutes_total: int
    orders: list[OrderListItem]
