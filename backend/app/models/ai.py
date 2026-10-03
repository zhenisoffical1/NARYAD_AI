from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, str_enum, utcnow
from app.models.enums import AssessmentStatus, Verdict


class AiAssessment(Base):
    """Результат проверки закрытого наряда. После доработки появляется новая запись."""

    __tablename__ = "ai_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    status: Mapped[AssessmentStatus] = mapped_column(str_enum(AssessmentStatus, 12))
    mode: Mapped[str] = mapped_column(String(12))  # llm | mock
    verdict: Mapped[Verdict | None] = mapped_column(str_enum(Verdict, 24))
    score_0_100: Mapped[int | None]
    score_1_5: Mapped[int | None]  # оценка по фото
    confidence: Mapped[float | None]
    needs_master_review: Mapped[bool] = mapped_column(default=False)
    explanation_worker: Mapped[str | None] = mapped_column(Text)
    explanation_master: Mapped[str | None] = mapped_column(Text)
    checks: Mapped[list[Any] | None]
    master_override_score: Mapped[int | None]
    master_comment: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None]

    @property
    def final_score(self) -> int | None:
        """Балл с учётом правки мастера — его используют рейтинг и отчёты."""
        if self.master_override_score is not None:
            return self.master_override_score
        return self.score_0_100


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    model: Mapped[str] = mapped_column(String(60))
    latency_ms: Mapped[int]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    ok: Mapped[bool]
    error: Mapped[str | None] = mapped_column(Text)
    prompt_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
