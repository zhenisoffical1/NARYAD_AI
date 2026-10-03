"""Итог проверки: балл 0–100, вердикт, нужна ли проверка мастером."""

from dataclasses import dataclass

from app.models.enums import Verdict
from app.services.verification.facts import CheckResult

REWORK_SCORE = 60
LOW_CONFIDENCE = 0.6


@dataclass(frozen=True, slots=True)
class Aggregate:
    score: int
    verdict: Verdict | None  # None — ИИ не уверен, решает мастер
    needs_master_review: bool
    confidence: float


def aggregate(checks: list[CheckResult], confidence: float) -> Aggregate:
    score = max(0, min(100, 100 - sum(c.penalty for c in checks)))
    critical = any(c.critical for c in checks)

    if critical or score < REWORK_SCORE:
        # Критичные факты (нет фото, перерасход, работы не по проблеме) установлены уверенно
        return Aggregate(score, Verdict.REWORK, False, confidence)
    if confidence < LOW_CONFIDENCE:
        return Aggregate(score, None, True, confidence)
    if any(c.status in ("warn", "fail") for c in checks):
        return Aggregate(score, Verdict.ACCEPTED_WITH_REMARKS, False, confidence)
    return Aggregate(score, Verdict.ACCEPTED, False, confidence)
