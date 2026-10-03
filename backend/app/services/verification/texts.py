"""Шаблонные отчёты по наряду (mock-режим и запасной вариант при сбое LLM).

Тон для исполнителя — уважительный, на «вы», с конкретикой и цифрами.
"""

from app.models.enums import Verdict
from app.services.verification.aggregate import Aggregate
from app.services.verification.facts import CheckResult, ClosureFacts
from app.services.verification.format import duration
from app.services.verification.rules import work_minutes

VERDICT_LABELS = {
    Verdict.ACCEPTED: "принято",
    Verdict.ACCEPTED_WITH_REMARKS: "принято с замечаниями",
    Verdict.REWORK: "требует доработки",
}


def _good_points(f: ClosureFacts, checks: list[CheckResult]) -> list[str]:
    by_key = {c.key: c for c in checks}
    good = []
    if by_key.get("works_match") and by_key["works_match"].status == "ok":
        good.append("работы точно закрывают заявленную проблему")
    if by_key.get("materials") and by_key["materials"].status == "ok":
        good.append("расход материалов в норме")
    if by_key.get("time") and by_key["time"].status == "ok":
        good.append("уложились в срок")
    if by_key.get("photos") and by_key["photos"].status == "ok":
        good.append("фото «после» подтверждает результат")
    if len(f.works_done) >= 60:
        good.append("подробно описали выполненные работы")
    return good


def worker_report(f: ClosureFacts, checks: list[CheckResult], result: Aggregate) -> str:
    lines = [f"Наряд №{f.number}: {result.score} из 100."]
    if result.verdict is not None:
        lines[0] += f" Итог: {VERDICT_LABELS[result.verdict]}."
    else:
        lines[0] += " Итог выставит мастер после проверки."

    good = _good_points(f, checks)
    if good:
        lines.append("Хорошо: " + "; ".join(good) + ".")

    remarks = [item for c in checks for item in c.items]
    if remarks:
        lines.append("Что улучшить:")
        lines += [f"— {r}" for r in remarks[:4]]
    elif result.verdict == Verdict.ACCEPTED:
        lines.append("Замечаний нет — спасибо за аккуратную работу.")

    actual = work_minutes(f)
    if f.norm_hours:
        lines.append(
            f"Время: {duration(actual)} при нормативе {duration(float(f.norm_hours) * 60)}."
        )
    else:
        lines.append(f"Время работы: {duration(actual)}.")
    return "\n".join(lines)


def master_report(f: ClosureFacts, checks: list[CheckResult], result: Aggregate) -> str:
    if result.verdict is None:
        head = (
            f"ИИ не уверен в оценке (уверенность {round(result.confidence * 100)}%) — "
            "нужна проверка мастером."
        )
    else:
        head = f"Вердикт ИИ: {VERDICT_LABELS[result.verdict]}, {result.score} из 100."
    lines = [head]
    for c in checks:
        mark = {"ok": "в норме", "warn": "замечание", "fail": "не пройдено", "skip": "—"}[c.status]
        lines.append(f"{c.label}: {mark}. {c.detail}")
    if result.verdict == Verdict.REWORK:
        reasons = [c.detail for c in checks if c.critical] or [
            c.detail for c in checks if c.status != "ok"
        ]
        lines.append("Вернуть на доработку: " + " ".join(reasons[:2]))
    return "\n".join(lines)
