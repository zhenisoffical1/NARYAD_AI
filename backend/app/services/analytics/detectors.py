"""Детекторы аномалий (CLAUDE.md, раздел 6.4). Каждый возвращает факты с цифрами.

Детектор ничего не «придумывает»: он считает по таблице нарядов и формулирует находку
словами с теми же цифрами. Модель потом может переписать вывод проще и добавить
рекомендацию, но цифры приходят отсюда.
"""

import math
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal

import pandas as pd

from app.services.analytics.data import Frames, Scope

Severity = Literal["high", "medium", "info"]


@dataclass
class Finding:
    kind: str
    title: str
    subject: str  # о чём находка: оборудование, участок, исполнитель
    severity: Severity
    facts: str  # факты с цифрами — одним-двумя предложениями
    recommendation: str
    numbers: dict[str, Any] = field(default_factory=dict)
    # Данные мини-графика: [{"label": …, "value": …, "accent": bool}]
    series: list[dict[str, Any]] = field(default_factory=list)
    chart: Literal["bars", "weeks", "pair"] = "bars"
    refs: dict[str, int] = field(default_factory=dict)  # equipment_id / section_id / worker_id


def num(value: float, digits: int = 1) -> str:
    """3.2 → «3,2», 3.0 → «3» — как пишут в отчётах на русском."""
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def times(ratio: float) -> str:
    return f"в {num(ratio)} раза"


def plural(n: int, one: str, few: str, many: str) -> str:
    """Русское согласование: 1 поломка, 3 поломки, 5 поломок, 21 поломка."""
    tail = n % 100
    if 11 <= tail <= 14:
        return many
    return {1: one, 2: few, 3: few, 4: few}.get(n % 10, many)


def lines_text(n: int) -> str:
    return f"{n} {plural(n, 'списание', 'списания', 'списаний')}"


BREAKDOWNS = ("внеплановая поломка", "внеплановые поломки", "внеплановых поломок")
TIMES = ("раз", "раза", "раз")


def binomial_tail(k: int, n: int, p: float) -> float:
    """P(X ≥ k) для X ~ Bin(n, p): насколько вероятно столько совпадений случайно."""
    p = min(max(p, 0.01), 0.99)
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def poisson_tail(k: int, lam: float) -> float:
    """P(X ≥ k) для X ~ Pois(lam): вероятность такого всплеска при прежнем темпе."""
    return 1 - sum(math.exp(-lam) * lam**i / math.factorial(i) for i in range(k))


def _weeks(frame: pd.DataFrame, scope: Scope, count: int = 12) -> list[dict[str, Any]]:
    """Число нарядов по неделям: последние `count` недель, от старых к новым."""
    end = pd.Timestamp(scope.end)
    result = []
    for i in range(count, 0, -1):
        start = end - pd.Timedelta(weeks=i)
        stop = start + pd.Timedelta(weeks=1)
        n = int(((frame["created_at"] >= start) & (frame["created_at"] < stop)).sum())
        result.append({"label": stop.strftime("%d.%m"), "value": n, "accent": i <= 4})
    return result


# --- 1. Проблемное оборудование -------------------------------------------------------


def problem_equipment(f: Frames, scope: Scope) -> list[Finding]:
    """Оборудование, где внеплановых поломок вдвое и больше выше среднего."""
    df = f.orders
    if df.empty:
        return []
    unplanned = df[df["unplanned"]]
    counts = unplanned.groupby("equipment_id").size()
    if len(counts) < 3:
        return []
    total, n = int(counts.sum()), len(counts)
    recent_start = pd.Timestamp(scope.end - timedelta(days=30))

    findings = []
    for equipment_id, count in counts.sort_values(ascending=False).items():
        # Сравнение с остальным оборудованием: сам выброс не должен тянуть среднее вверх
        mean = (total - count) / (n - 1)
        ratio = count / mean
        if ratio < 2:
            break
        rows = unplanned[unplanned["equipment_id"] == equipment_id]
        recent = rows[rows["created_at"] >= recent_start]
        codes = recent["code"].value_counts()
        top_code = str(codes.index[0]) if not codes.empty else None
        top_name = str(recent[recent["code"] == top_code]["code_name"].iloc[0]) if top_code else ""
        downtime = int(rows["downtime"].sum())
        name = str(rows["equipment"].iloc[0])
        facts = (
            f"{name}: {count} {plural(int(count), *BREAKDOWNS)} за {scope.days} дн. — "
            f"{times(ratio)} больше среднего по остальному оборудованию ({num(mean)}). "
            f"За последние 30 дней — {len(recent)}"
        )
        if top_code:
            facts += f", из них {int(codes.iloc[0])} по шифру {top_code} «{top_name}»"
        facts += f". Простой — {num(downtime / 60)} ч."
        findings.append(
            Finding(
                kind="problem_equipment",
                title="Проблемное оборудование",
                subject=name,
                severity="high" if ratio >= 3 or len(recent) >= count / 2 else "medium",
                facts=facts,
                recommendation=(
                    f"Провести внеплановую диагностику узла по шифру {top_code} "
                    f"(«{top_name.lower()}»), проверить условия работы и сменить поставщика "
                    "запчастей, если отказы повторяются после замены."
                    if top_code
                    else "Провести внеплановую диагностику оборудования."
                ),
                numbers={
                    "count": int(count),
                    "mean": round(mean, 1),
                    "ratio": round(ratio, 2),
                    "recent": len(recent),
                    "top_code": top_code,
                    "top_code_count": int(codes.iloc[0]) if top_code else 0,
                    "downtime_hours": round(downtime / 60, 1),
                },
                series=_weeks(rows, scope),
                chart="weeks",
                refs={"equipment_id": int(equipment_id)},
            )
        )
    return findings


# --- 2. Исполнитель с частыми возвратами -----------------------------------------------

MIN_CLOSED = 5


def worker_returns(f: Frames, scope: Scope) -> list[Finding]:
    """Доля закрытых нарядов, вернувшихся на доработку или с повторной поломкой ≤7 дней."""
    df = f.orders
    if df.empty:
        return []
    closed = df[(df["status"] == "CLOSED") & df["assignee_id"].notna()].copy()
    closed["returned"] = closed["rework"] | closed["repeat"]
    stats = closed.groupby(["assignee_id", "assignee"]).agg(
        n=("id", "size"), returned=("returned", "sum")
    )
    stats = stats[stats["n"] >= MIN_CLOSED]
    if len(stats) < 3:
        return []
    stats["rate"] = stats["returned"] / stats["n"]

    findings = []
    for (worker_id, name), row in stats.sort_values("rate", ascending=False).iterrows():
        others = stats.drop(index=(worker_id, name))
        others_rate = float(others["returned"].sum() / others["n"].sum())
        rate = float(row["rate"])
        if rate < 0.2 or rate < 2.5 * max(others_rate, 0.01):
            break
        findings.append(
            Finding(
                kind="worker_returns",
                title="Частые возвраты после работ",
                subject=str(name),
                severity="high",
                facts=(
                    f"{name}: {int(row['returned'])} из {int(row['n'])} закрытых нарядов "
                    f"({round(rate * 100)}%) вернулись на доработку или оборудование сломалось "
                    f"снова в течение 7 дней. У остальных исполнителей — "
                    f"{round(others_rate * 100)}%."
                ),
                recommendation=(
                    "Разобрать с исполнителем последние возвраты, проверить знание регламентов "
                    "и на месяц назначить контрольную приёмку его нарядов мастером."
                ),
                numbers={
                    "rate": round(rate, 3),
                    "others_rate": round(others_rate, 3),
                    "returned": int(row["returned"]),
                    "closed": int(row["n"]),
                },
                series=[
                    {"label": str(name), "value": round(rate * 100), "accent": True},
                    {"label": "остальные", "value": round(others_rate * 100), "accent": False},
                ],
                chart="pair",
                refs={"worker_id": int(worker_id)},
            )
        )
    return findings


# --- 3. Поломки вскоре после ППР ------------------------------------------------------

PPR_WINDOW = timedelta(days=7)


def after_ppr(f: Frames, scope: Scope) -> list[Finding]:
    """Для оборудования и бригады: как часто за ППР следует поломка в течение 7 дней."""
    df = f.orders
    if df.empty:
        return []
    data_end = df["created_at"].max()
    pprs = df[df["planned"] & df["done_at"].notna() & df["brigade"].notna()]
    breakdowns = df[df["unplanned"]]

    rows = []
    for _, ppr in pprs.iterrows():
        window_end = ppr["done_at"] + PPR_WINDOW
        if window_end > data_end:
            continue  # окно наблюдения ещё не закрылось
        same = breakdowns[breakdowns["equipment_id"] == ppr["equipment_id"]]
        after = (same["created_at"] > ppr["done_at"]) & (same["created_at"] <= window_end)
        rows.append(
            {
                "equipment_id": ppr["equipment_id"],
                "equipment": ppr["equipment"],
                "brigade": ppr["brigade"],
                "hit": bool(after.any()),
            }
        )
    if not rows:
        return []
    table = pd.DataFrame(rows)
    baseline = float(table["hit"].mean())

    findings = []
    for (equipment_id, equipment, brigade), group in table.groupby(
        ["equipment_id", "equipment", "brigade"]
    ):
        total, hits = len(group), int(group["hit"].sum())
        share = hits / total
        others = table[(table["equipment_id"] == equipment_id) & (table["brigade"] != brigade)]
        other_share = float(others["hit"].mean()) if len(others) else baseline
        # Значимость: при такой базовой частоте совпадение не должно быть случайным (p < 0,05)
        if hits < 3 or share - other_share < 0.4 or binomial_tail(hits, total, other_share) > 0.05:
            continue
        other_text = (
            f"после ППР других бригад — {int(others['hit'].sum())} из {len(others)}"
            if len(others)
            else f"в среднем по заводу — {round(baseline * 100)}%"
        )
        findings.append(
            Finding(
                kind="after_ppr",
                title="Поломки вскоре после ППР",
                subject=str(equipment),
                severity="high",
                facts=(
                    f"{equipment}: после ППР, выполненных бригадой «{brigade}», внеплановая "
                    f"поломка в течение 7 дней случилась {hits} {plural(hits, *TIMES)} "
                    f"из {total}; {other_text}."
                ),
                recommendation=(
                    f"Проверить технологическую карту ППР и качество работ бригады «{brigade}»: "
                    "моменты затяжки, смазку, регулировку. Ближайший ППР провести с приёмкой "
                    "механиком."
                ),
                numbers={
                    "brigade": str(brigade),
                    "share": round(share, 2),
                    "other_share": round(other_share, 2),
                    "hits": hits,
                    "total": total,
                },
                series=[
                    {"label": str(brigade), "value": round(share * 100), "accent": True},
                    {"label": "другие", "value": round(other_share * 100), "accent": False},
                ],
                chart="pair",
                refs={"equipment_id": int(equipment_id)},
            )
        )
    return findings


# --- 4. Связь со сменой и временем суток ------------------------------------------------

GROUP_NAMES = {
    "М": "механические",
    "Э": "электрические",
    "Г": "гидравлические",
    "П": "пневматические",
    "С": "смазочные",
}


def night_shift(f: Frames, scope: Scope) -> list[Finding]:
    """Участок × вид отказа, где ночью ломается намного чаще, чем днём (смены по 12 ч)."""
    df = f.orders
    if df.empty:
        return []
    unplanned = df[df["unplanned"] & df["code_group"].notna()]
    findings = []
    for (section_id, section, group), rows in unplanned.groupby(
        ["section_id", "section", "code_group"]
    ):
        night = int(rows["night"].sum())
        day = len(rows) - night
        if day < 5 or night < 10:
            continue
        ratio = night / day
        if ratio < 2:
            continue
        kind_name = GROUP_NAMES.get(str(group), str(group))
        findings.append(
            Finding(
                kind="night_shift",
                title="Отказы в ночную смену",
                subject=str(section),
                severity="high" if ratio >= 2.5 else "medium",
                facts=(
                    f"Участок «{section}»: {kind_name} отказы (шифры {group}-*) ночью — {night}, "
                    f"днём — {day}, то есть {times(ratio)} чаще в ночную смену."
                ),
                recommendation=(
                    "Проверить ночной режим работы оборудования (нагрузку, нагрев, состояние "
                    "щитовых), состав и допуски ночной смены; поставить в ночь дежурного "
                    "электромонтёра."
                    if group == "Э"
                    else "Проверить режим работы и состав ночной смены на этом участке."
                ),
                numbers={
                    "group": str(group),
                    "night": night,
                    "day": day,
                    "ratio": round(ratio, 2),
                },
                series=[
                    {"label": "ночь", "value": night, "accent": True},
                    {"label": "день", "value": day, "accent": False},
                ],
                chart="pair",
                refs={"section_id": int(section_id)},
            )
        )
    return findings


# --- 5. Перерасход материалов ---------------------------------------------------------

MIN_LINES = 3


def material_overuse(f: Frames, scope: Scope) -> list[Finding]:
    """Исполнитель × категория материалов: средний расход к норме против остальных."""
    lines = f.materials
    if lines.empty:
        return []
    stats = (
        lines.groupby(["worker_id", "worker", "category"])
        .agg(n=("ratio", "size"), ratio=("ratio", "mean"))
        .reset_index()
    )
    stats = stats[stats["n"] >= MIN_LINES]
    findings = []
    for category, group in stats.groupby("category"):
        if len(group) < 3:
            continue
        for _, row in group.iterrows():
            others = group[group["worker_id"] != row["worker_id"]]
            mean = float(others["ratio"].mean())
            std = float(others["ratio"].std() or 0.0)
            ratio = float(row["ratio"])
            z = (ratio - mean) / max(std, 0.05)
            if ratio < 1.6 or ratio < 1.5 * mean or z < 3:
                continue
            findings.append(
                Finding(
                    kind="material_overuse",
                    title="Перерасход материалов",
                    subject=str(row["worker"]),
                    severity="high" if ratio >= 2 else "medium",
                    facts=(
                        f"{row['worker']}: {category} материалы списываются в среднем "
                        f"{times(ratio)} больше нормы ({lines_text(int(row['n']))}). "
                        f"У остальных исполнителей — {num(mean, 2)} нормы."
                    ),
                    recommendation=(
                        "Сверить расход с остатками на складе, выборочно проверить списания "
                        "и при подтверждении провести инструктаж по нормам расхода."
                    ),
                    numbers={
                        "category": str(category),
                        "ratio": round(ratio, 2),
                        "others": round(mean, 2),
                        "lines": int(row["n"]),
                        "z": round(z, 1),
                    },
                    series=[
                        {"label": str(row["worker"]), "value": round(ratio, 2), "accent": True},
                        {"label": "остальные", "value": round(mean, 2), "accent": False},
                    ],
                    chart="pair",
                    refs={"worker_id": int(row["worker_id"])},
                )
            )
    return findings


# --- 6. Повтор одного шифра на одном оборудовании ----------------------------------------


def repeat_fault(f: Frames, scope: Scope) -> list[Finding]:
    """Пары «оборудование + шифр», где одна и та же поломка возвращается раз за разом."""
    df = f.orders
    if df.empty:
        return []
    unplanned = df[df["unplanned"] & df["code"].notna()]
    pairs = unplanned.groupby(["equipment_id", "equipment", "code", "code_name"]).size()
    if pairs.empty:
        return []
    median = float(pairs.median())
    findings = []
    for (equipment_id, equipment, code, code_name), count in pairs.sort_values(
        ascending=False
    ).items():
        if count < max(6, 3 * median):
            break
        rows = unplanned[(unplanned["equipment_id"] == equipment_id) & (unplanned["code"] == code)]
        gaps = rows["created_at"].sort_values().diff().dropna()
        mean_gap = float(gaps.mean().total_seconds() / 86400) if len(gaps) else 0.0
        findings.append(
            Finding(
                kind="repeat_fault",
                title="Повторяющаяся поломка",
                subject=f"{equipment}, {code}",
                severity="medium",
                facts=(
                    f"{equipment}: шифр {code} «{code_name}» — {count} "
                    f"{plural(int(count), *TIMES)} за {scope.days} дн., в среднем раз в "
                    f"{num(mean_gap)} дн. Обычно одна поломка на одном оборудовании "
                    f"повторяется {num(median)} {plural(round(median), *TIMES)} за период."
                ),
                recommendation=(
                    "Устранять причину, а не следствие: проверить соосность, нагрузку и качество "
                    "запчастей; рассмотреть замену узла целиком."
                ),
                numbers={
                    "count": int(count),
                    "median": median,
                    "mean_gap_days": round(mean_gap, 1),
                    "code": str(code),
                },
                series=_weeks(rows, scope),
                chart="weeks",
                refs={"equipment_id": int(equipment_id)},
            )
        )
    return findings[:3]


# --- 7. Тренд роста внеплановых → прогноз риска ------------------------------------------


def growth_trend(f: Frames, scope: Scope) -> list[Finding]:
    """Оборудование, где за последние 4 недели поломок заметно больше, чем раньше."""
    df = f.orders
    if df.empty or scope.days < 56:
        return []
    unplanned = df[df["unplanned"]]
    recent_start = pd.Timestamp(scope.end) - pd.Timedelta(weeks=4)
    earlier_weeks = (scope.days - 28) / 7
    findings = []
    for (equipment_id, equipment), rows in unplanned.groupby(["equipment_id", "equipment"]):
        recent = int((rows["created_at"] >= recent_start).sum())
        earlier = (len(rows) - recent) / earlier_weeks  # поломок в неделю раньше
        per_week = recent / 4
        expected = max(earlier, 0.25) * 4
        if (
            recent < 8
            or per_week < 2 * max(earlier, 0.25)
            or poisson_tail(recent, expected) > 0.002
        ):
            continue
        forecast = round(per_week * 4)
        findings.append(
            Finding(
                kind="growth_trend",
                title="Рост поломок — риск отказа",
                subject=str(equipment),
                severity="high",
                facts=(
                    f"{equipment}: за последние 4 недели {recent} {plural(recent, *BREAKDOWNS)} — "
                    f"{num(per_week)} в неделю против {num(earlier)} раньше "
                    f"({times(per_week / max(earlier, 0.01))} больше). При том же темпе — "
                    f"около {forecast} поломок в следующие 4 недели."
                ),
                recommendation=(
                    "Включить оборудование в ближайший ППР внепланово, заказать запас запчастей "
                    "по основным шифрам и предупредить смежные участки о риске простоя."
                ),
                numbers={
                    "recent": recent,
                    "per_week": round(per_week, 2),
                    "earlier_per_week": round(earlier, 2),
                    "forecast": forecast,
                },
                series=_weeks(rows, scope),
                chart="weeks",
                refs={"equipment_id": int(equipment_id)},
            )
        )
    return findings


# --- обзор среза — ответ на любой вопрос, даже если аномалий нет -------------------------


def overview(f: Frames, scope: Scope) -> list[Finding]:
    df = f.orders
    unplanned = df[df["unplanned"]] if not df.empty else df
    count = len(unplanned)
    downtime = int(unplanned["downtime"].sum()) if count else 0
    facts = f"За {scope.days} дн.: {count} {plural(count, *BREAKDOWNS)}"
    numbers: dict[str, Any] = {"count": count, "downtime_hours": round(downtime / 60, 1)}
    if count:
        codes = unplanned.groupby(["code", "code_name"]).size().sort_values(ascending=False)
        (code, name), top = codes.index[0], int(codes.iloc[0])
        facts += (
            f", простой {num(downtime / 60)} ч. Чаще всего — шифр {code} «{name}» "
            f"({top} {plural(top, *TIMES)})."
        )
        numbers |= {"top_code": code, "top_code_count": top}
    else:
        facts += "."
    return [
        Finding(
            kind="overview",
            title="Сводка за период",
            subject="",
            severity="info",
            facts=facts,
            recommendation="",
            numbers=numbers,
            series=_weeks(unplanned, scope) if count else [],
            chart="weeks",
        )
    ]


DETECTORS = (
    problem_equipment,
    worker_returns,
    after_ppr,
    night_shift,
    material_overuse,
    repeat_fault,
    growth_trend,
)
