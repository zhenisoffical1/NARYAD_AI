"""Схемы подсказок, рейтинга и уведомлений."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import OrderType, Priority
from app.schemas.common import ORMModel, PersonShort, RefShort
from app.schemas.orders import PersonStatus


class AssistRequest(BaseModel):
    equipment_id: int
    description: str = Field(default="", max_length=4000)
    priority: Priority | None = None


class CandidateOut(BaseModel):
    person: PersonStatus
    specialty: str | None
    grade: int | None
    specialty_match: bool
    equipment_score: float | None
    reason: str
    recommended: bool


class FaultSuggestionOut(BaseModel):
    id: int
    code: str
    name: str
    norm_hours: Decimal | None
    confidence: float


class AssistOut(BaseModel):
    specialty: str
    fault_code: FaultSuggestionOut | None
    order_type: OrderType
    deadline_hours: float
    candidates: list[CandidateOut]


class ComponentOut(BaseModel):
    key: str
    label: str
    weight: float
    value: float
    points: float
    potential: float
    detail: str


class WorkerRatingOut(BaseModel):
    employee: PersonShort
    brigade_id: int | None
    orders: int
    score: float | None
    rank: int | None
    components: list[ComponentOut]
    explanation: str


class BrigadeRatingOut(BaseModel):
    brigade: RefShort
    members: int
    orders: int
    score: float | None
    components: list[ComponentOut]


class RatingReportOut(BaseModel):
    period_start: datetime
    period_end: datetime
    workers: list[WorkerRatingOut]
    brigades: list[BrigadeRatingOut]


class MyRatingOut(WorkerRatingOut):
    total_rated: int
    period_start: datetime
    period_end: datetime


class NotificationOut(ORMModel):
    id: int
    kind: str
    title: str
    body: str
    order_id: int | None
    urgent: bool = False
    data: dict[str, Any] | None = None
    created_at: datetime
    read_at: datetime | None


class NotificationFeed(BaseModel):
    items: list[NotificationOut]
    unread: int


class MarkRead(BaseModel):
    ids: list[int] | None = None  # None — отметить все
