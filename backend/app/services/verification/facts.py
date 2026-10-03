"""Факты о закрытом наряде — вход для правил и LLM. Не зависят от ORM, поэтому легко тестируются."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.models.enums import OrderType, Priority

CheckStatus = Literal["ok", "warn", "fail", "skip"]


@dataclass(frozen=True, slots=True)
class MaterialFact:
    name: str
    unit: str
    quantity: Decimal
    category: str | None
    norm_quantity: Decimal | None  # норма расхода по шифру; None — материала нет в нормативе


@dataclass(frozen=True, slots=True)
class ClosureFacts:
    number: int
    order_type: OrderType
    priority: Priority
    equipment: str
    equipment_type: str
    description: str
    works_done: str
    fault_code: str  # «Г-02»
    fault_name: str
    norm_hours: Decimal | None
    norm_materials: tuple[tuple[str, str, Decimal], ...]  # (название, ед., норма)
    no_materials: bool
    materials: tuple[MaterialFact, ...]
    after_photos: int
    before_photos: int
    issued_at: datetime
    started_at: datetime | None
    done_at: datetime
    deadline_at: datetime
    paused_minutes: int = 0
    comment: str | None = None
    # Наряд из истории, перенесённой в систему: фото к нему не загружались
    archive: bool = False


@dataclass(slots=True)
class CheckResult:
    key: str
    label: str
    status: CheckStatus
    detail: str
    critical: bool = False  # провал, который сам по себе отправляет на доработку
    penalty: int = 0  # сколько баллов из 100 снимает эта проверка
    items: list[str] = field(default_factory=list)  # конкретные замечания

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "critical": self.critical,
            "penalty": self.penalty,
            "items": self.items,
        }
