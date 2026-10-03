"""Проверка тестовых данных: статистика и подтверждение пяти заложенных закономерностей.

Запуск: python -m seed.check

Это независимый «эталон»: считает закономерности напрямую по таблицам, без детекторов
аналитики. Тест детекторов сравнивает свои выводы с этими цифрами.
"""

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import SessionLocal
from app.models import (
    AiAssessment,
    Brigade,
    Employee,
    Equipment,
    FaultCode,
    Order,
    Section,
    TimeNorm,
    TimeNormMaterial,
)
from app.models.enums import OrderStatus, OrderType, Shift
from app.services.shifts import shift_of
from app.services.verification.format import num
from seed.demo import get_history_end
from seed.history import PatternConfig
from seed.reference_data import LUBRICANT_CATEGORY


@dataclass
class PatternResult:
    name: str
    passed: bool
    summary: str
    numbers: dict[str, float] = field(default_factory=dict)


@dataclass
class Report:
    stats: dict[str, object]
    patterns: list[PatternResult]

    @property
    def all_passed(self) -> bool:
        return all(p.passed for p in self.patterns)


async def _history(session: AsyncSession) -> list[Order]:
    end = await get_history_end(session)
    stmt = select(Order).options(
        selectinload(Order.events),
        selectinload(Order.writeoffs),
        selectinload(Order.equipment),
        selectinload(Order.fault_code),
    )
    if end is not None:
        stmt = stmt.where(Order.created_at < end)
    return list(await session.scalars(stmt))


def k3_pattern(orders: list[Order], cfg: PatternConfig) -> PatternResult:
    unplanned = [o for o in orders if o.type == OrderType.UNPLANNED]
    by_eq = Counter(o.equipment.inv_number for o in unplanned)
    all_inv = {o.equipment.inv_number for o in orders}
    others = [by_eq.get(inv, 0) for inv in all_inv if inv != cfg.k3_inv]
    mean = sum(others) / len(others)
    k3 = by_eq.get(cfg.k3_inv, 0)
    end = max(o.created_at for o in orders)
    recent = [
        o
        for o in unplanned
        if o.equipment.inv_number == cfg.k3_inv and o.created_at >= end - timedelta(days=30)
    ]
    bearing = sum(1 for o in recent if o.fault_code and o.fault_code.code == "М-02")
    ratio = k3 / mean if mean else 0
    passed = ratio >= 2.5 and len(recent) >= k3 * 0.5 and bearing >= len(recent) * 0.6
    return PatternResult(
        "1. Конвейер К-3 ломается чаще остальных",
        passed,
        f"К-3: {k3} внеплановых против среднего {num(mean, 1)} (в {num(ratio, 1)} раза); "
        f"за последние 30 дней — {len(recent)}, из них М-02 (подшипник) — {bearing}",
        {"k3": k3, "mean_others": round(mean, 2), "ratio": round(ratio, 2), "recent": len(recent),
         "recent_bearing": bearing},
    )  # fmt: skip


def chronic_pairs(orders: list[Order]) -> set[tuple[int, int]]:
    """(оборудование, шифр), которые ломаются постоянно: это проблема узла, а не исполнителя."""
    counts = Counter(
        (o.equipment_id, o.fault_code_id)
        for o in orders
        if o.type == OrderType.UNPLANNED and o.fault_code_id
    )
    if not counts:
        return set()
    values = sorted(counts.values())
    median = values[len(values) // 2]
    return {pair for pair, n in counts.items() if n >= max(8, 3 * median)}


def returns_pattern(
    orders: list[Order], workers: dict[int, Employee], cfg: PatternConfig
) -> PatternResult:
    unplanned_by_eq: dict[int, list[Order]] = defaultdict(list)
    for o in orders:
        if o.type == OrderType.UNPLANNED:
            unplanned_by_eq[o.equipment_id].append(o)
    chronic = chronic_pairs(orders)

    closed: Counter[int] = Counter()
    returned: Counter[int] = Counter()
    for o in orders:
        if o.status != OrderStatus.CLOSED or o.assignee_id is None or o.done_at is None:
            continue
        closed[o.assignee_id] += 1
        rework = any(e.to_status == OrderStatus.REWORK for e in o.events)
        repeat = (
            o.type == OrderType.UNPLANNED and (o.equipment_id, o.fault_code_id) not in chronic
        ) and any(
            later.id != o.id
            and later.fault_code_id == o.fault_code_id
            and o.done_at < later.created_at <= o.done_at + timedelta(days=7)
            for later in unplanned_by_eq[o.equipment_id]
        )
        if rework or repeat:
            returned[o.assignee_id] += 1

    rates = {wid: returned[wid] / closed[wid] for wid in closed if closed[wid] >= 5}
    target = next(w for w in workers.values() if w.login == cfg.returns_login)
    target_rate = rates.get(target.id, 0.0)
    others = [r for wid, r in rates.items() if wid != target.id]
    mean_others = sum(others) / len(others) if others else 0
    passed = target_rate >= 0.22 and target_rate >= 3 * mean_others
    return PatternResult(
        "2. Исполнитель с частыми возвратами",
        passed,
        f"{target.short_name}: {returned[target.id]} из {closed[target.id]} нарядов "
        f"({round(target_rate * 100)}%) — доработка или повторная поломка ≤7 дней; "
        f"у остальных в среднем {round(mean_others * 100)}%",
        {"rate": round(target_rate, 3), "mean_others": round(mean_others, 3)},
    )


def ppr_pattern(orders: list[Order], brigades: dict[int, str], cfg: PatternConfig) -> PatternResult:
    eq_orders = [o for o in orders if o.equipment.inv_number == cfg.ppr_inv]
    pprs = [o for o in eq_orders if o.type == OrderType.PLANNED and o.fault_code and
            o.fault_code.code != "Э-02" and o.done_at]  # fmt: skip
    breakdowns = [o for o in eq_orders if o.type == OrderType.UNPLANNED]
    data_end = max(o.created_at for o in orders)
    followed: Counter[str] = Counter()
    total: Counter[str] = Counter()
    for ppr in pprs:
        assert ppr.done_at is not None
        window_end = ppr.done_at + timedelta(days=cfg.ppr_breakdown_days)
        if window_end > data_end:
            continue  # окно наблюдения ещё не закрылось
        brigade = brigades.get(ppr.brigade_id or 0, "?")
        total[brigade] += 1
        if any(ppr.done_at < b.created_at <= window_end for b in breakdowns):
            followed[brigade] += 1
    b2, b1 = cfg.ppr_brigade, cfg.ppr_other_brigade
    share2 = followed[b2] / total[b2] if total[b2] else 0
    share1 = followed[b1] / total[b1] if total[b1] else 0
    passed = total[b2] >= 2 and share2 >= 0.75 and share1 <= 0.25
    return PatternResult(
        "3. Поломки КМД-1750 вскоре после ППР бригады №2",
        passed,
        f"КМД-1750: после ППР бригады №2 поломка в течение {cfg.ppr_breakdown_days} дней — "
        f"{followed[b2]} из {total[b2]}; после ППР бригады №1 — {followed[b1]} из {total[b1]}",
        {"share_brigade2": round(share2, 2), "share_brigade1": round(share1, 2)},
    )


def night_pattern(
    orders: list[Order], sections: dict[int, str], cfg: PatternConfig
) -> PatternResult:
    group = [
        o
        for o in orders
        if o.type == OrderType.UNPLANNED
        and sections[o.section_id] == cfg.night_section
        and o.fault_code
        and o.fault_code.code.startswith("Э")
    ]
    night = sum(1 for o in group if shift_of(o.created_at) == Shift.NIGHT)
    day = len(group) - night
    ratio = night / day if day else float(night)
    passed = ratio >= 2.0
    return PatternResult(
        "4. Электрические отказы на обогащении ночью",
        passed,
        f"Обогащение, шифры Э-*: ночью {night}, днём {day} (в {num(ratio, 1)} раза чаще ночью)",
        {"night": night, "day": day, "ratio": round(ratio, 2)},
    )


def lube_pattern(
    orders: list[Order],
    workers: dict[int, Employee],
    norms: dict[int, dict[int, Decimal]],
    lubricants: set[int],
    cfg: PatternConfig,
) -> PatternResult:
    ratios: dict[int, list[float]] = defaultdict(list)
    for o in orders:
        if o.assignee_id is None or o.fault_code_id is None:
            continue
        norm = norms.get(o.fault_code_id, {})
        for w in o.writeoffs:
            if w.material_id in lubricants and norm.get(w.material_id):
                ratios[o.assignee_id].append(float(w.quantity / norm[w.material_id]))
    averages = {wid: sum(r) / len(r) for wid, r in ratios.items() if len(r) >= 3}
    target = next(w for w in workers.values() if w.login == cfg.lube_login)
    target_avg = averages.get(target.id, 0.0)
    others = [a for wid, a in averages.items() if wid != target.id]
    mean_others = sum(others) / len(others) if others else 0
    passed = target_avg >= 1.9 and mean_others <= 1.3
    return PatternResult(
        "5. Перерасход смазочных материалов",
        passed,
        f"{target.short_name}: смазочные в среднем {num(target_avg, 1)} нормы "
        f"({len(ratios[target.id])} списаний); у остальных — {num(mean_others, 2)} нормы",
        {"ratio": round(target_avg, 2), "mean_others": round(mean_others, 2)},
    )


async def collect(session: AsyncSession, cfg: PatternConfig | None = None) -> Report:
    cfg = cfg or PatternConfig()
    orders = await _history(session)
    workers = {e.id: e for e in await session.scalars(select(Employee))}
    sections = {s.id: s.name for s in await session.scalars(select(Section))}
    brigades = {b.id: b.name for b in await session.scalars(select(Brigade))}
    norms: dict[int, dict[int, Decimal]] = defaultdict(dict)
    for norm in await session.scalars(select(TimeNorm).options(selectinload(TimeNorm.materials))):
        for line in norm.materials:
            norms[norm.fault_code_id][line.material_id] = line.quantity
    lubricants = {
        m.material_id
        for m in await session.scalars(
            select(TimeNormMaterial).options(selectinload(TimeNormMaterial.material))
        )
        if m.material.category == LUBRICANT_CATEGORY
    }
    assessments = list(await session.scalars(select(AiAssessment)))

    first = min(o.created_at for o in orders)
    last = max(o.created_at for o in orders)
    stats: dict[str, object] = {
        "нарядов": len(orders),
        "период": f"{first:%d.%m.%Y} — {last:%d.%m.%Y} ({(last - first).days} дн.)",
        "по типу": dict(Counter(o.type.value for o in orders)),
        "по приоритету": dict(Counter(o.priority.value for o in orders)),
        "по статусу": dict(Counter(o.status.value for o in orders)),
        "по участкам": dict(Counter(sections[o.section_id] for o in orders)),
        "оборудования": await session.scalar(select(Equipment.id).order_by(Equipment.id.desc())),
        "шифров": len(list(await session.scalars(select(FaultCode.id)))),
        "событий журнала": sum(len(o.events) for o in orders),
        "оценки ИИ": dict(Counter(str(a.verdict) for a in assessments)),
        "с простоем": sum(1 for o in orders if o.downtime_minutes),
    }
    patterns = [
        k3_pattern(orders, cfg),
        returns_pattern(orders, workers, cfg),
        ppr_pattern(orders, brigades, cfg),
        night_pattern(orders, sections, cfg),
        lube_pattern(orders, workers, norms, lubricants, cfg),
    ]
    return Report(stats, patterns)


async def main() -> int:
    async with SessionLocal() as session:
        report = await collect(session)
    print("Статистика истории")
    for key, value in report.stats.items():
        print(f"  {key}: {value}")
    print("\nЗаложенные закономерности")
    for p in report.patterns:
        print(f"  [{'OK' if p.passed else 'НЕТ'}] {p.name}\n        {p.summary}")
    print("\nВсе закономерности на месте." if report.all_passed else "\nЕсть проблемы — см. выше.")
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
