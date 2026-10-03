"""Соответствие выполненных работ проблеме и шифру.

Основной путь — LLM (см. llm_works_match). Без ключа и при сбое API — тематическое сравнение:
грубее, но воспроизводимо и честно сообщает о низкой уверенности.
"""

from dataclasses import dataclass

from app.models.enums import OrderType
from app.services.verification.facts import CheckResult, ClosureFacts
from app.services.verification.topics import overlap

OK_THRESHOLD = 0.5
FAIL_THRESHOLD = 0.25


@dataclass(frozen=True, slots=True)
class WorksMatch:
    check: CheckResult
    score: float  # 0..1
    confidence: float  # 0..1


def _check(score: float, reason: str) -> CheckResult:
    if score >= OK_THRESHOLD:
        return CheckResult("works_match", "Работы соответствуют проблеме", "ok", reason)
    if score >= FAIL_THRESHOLD:
        return CheckResult(
            "works_match", "Работы соответствуют проблеме", "warn", reason, False, 15, [reason]
        )
    return CheckResult(
        "works_match", "Работы соответствуют проблеме", "fail", reason, True, 40, [reason]
    )


def mock_works_match(f: ClosureFacts) -> WorksMatch:
    if f.order_type == OrderType.PLANNED:
        reason = "Плановые работы по графику ППР — сверяются с регламентом, а не с заявкой."
        return WorksMatch(_check(1.0, reason), 1.0, 0.8)

    by_description, problem, works = overlap(f.description, f.works_done)
    by_code, code_topics, _ = overlap(f.fault_name, f.works_done)
    score = max(by_description, by_code)

    if not works:
        reason = (
            "В описании работ не названы узлы и операции — не видно, что именно сделано "
            f"по проблеме «{f.description[:80]}»."
        )
        return WorksMatch(_check(min(score, 0.4), reason), min(score, 0.4), 0.55)

    expected = problem or code_topics
    if score >= OK_THRESHOLD:
        common = ", ".join(sorted((problem | code_topics) & works)) or "узел"
        reason = f"Работы закрывают заявленную проблему: {common}."
    else:
        reason = (
            f"Заявлено: {', '.join(sorted(expected)) or f.description[:60]}; "
            f"в работах: {', '.join(sorted(works))}. Работы не устраняют заявленную проблему."
        )
    confidence = 0.8 if expected else 0.55
    return WorksMatch(_check(score, reason), score, confidence)
