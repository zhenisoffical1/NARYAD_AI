"""Соответствие выполненных работ проблеме и шифру.

Основной путь — LLM (см. llm_works_match). Без ключа и при сбое API — тематическое сравнение:
грубее, но воспроизводимо и честно сообщает о низкой уверенности.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import OrderType
from app.services.llm import anonymize, ask_json, facts_json, prompt, text_block
from app.services.verification.facts import CheckResult, ClosureFacts
from app.services.verification.topics import overlap

OK_THRESHOLD = 0.5
FAIL_THRESHOLD = 0.25


@dataclass(frozen=True, slots=True)
class WorksMatch:
    check: CheckResult
    score: float  # 0..1
    confidence: float  # 0..1
    source: Literal["llm", "rules"] = "rules"


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


# --- LLM -----------------------------------------------------------------------


class WorksMatchOut(BaseModel):
    """Ответ модели. Границы проверяются здесь: API их не ограничивает."""

    match: float = Field(ge=0, le=1)
    materials_relevant: bool
    issues: list[str]
    reason: str = Field(max_length=400)
    confidence: float = Field(ge=0, le=1)


def _llm_facts(f: ClosureFacts, names: Iterable[str]) -> str:
    return facts_json(
        {
            "оборудование": f"{f.equipment} (тип: {f.equipment_type})",
            "тип наряда": "внеплановый" if f.order_type == OrderType.UNPLANNED else "плановый",
            "проблема": anonymize(f.description, names),
            "шифр": f"{f.fault_code} — {f.fault_name}",
            "что сделано": anonymize(f.works_done, names),
            "материалы": "без материалов"
            if f.no_materials
            else [f"{m.name} — {m.quantity} {m.unit}" for m in f.materials],
            "комментарий исполнителя": anonymize(f.comment, names) if f.comment else None,
        }
    )


async def works_match(f: ClosureFacts, names: Iterable[str] = ()) -> WorksMatch:
    """Соответствие работ: модель, а без неё или при сбое — тематическое сравнение."""
    fallback = mock_works_match(f)
    if f.order_type == OrderType.PLANNED:
        return fallback  # ППР сверяется с регламентом — модели тут нечего добавить
    out = await ask_json(
        "works_match",
        WorksMatchOut,
        system=prompt("works_match"),
        content=[text_block(_llm_facts(f, list(names)))],
    )
    if out is None:
        return fallback

    reason = out.reason.strip()
    check = _check(out.match, reason)
    check.items = [i.strip() for i in out.issues if i.strip()] or check.items
    if not out.materials_relevant and not f.no_materials:
        note = "Списанные материалы не соответствуют выполненным работам."
        check.items.append(note)
        check.penalty += 10
        if check.status == "ok":
            check.status = "warn"
    return WorksMatch(check, out.match, out.confidence, source="llm")
