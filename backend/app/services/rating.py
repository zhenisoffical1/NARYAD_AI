"""Рейтинг исполнителей и бригад — формула, понятная рабочим (CLAUDE.md, 6.5).

Веса в настройках, обоснование — docs/DECISIONS.md. Каждый получает разбор по
составляющим и подсказку, что поднимет рейтинг сильнее всего.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models import Brigade, Employee, Order, OrderEvent
from app.models.base import utcnow
from app.models.enums import Criticality, OrderStatus, OrderType, Role
from app.services.orders import latest_assessments
from app.services.quality import had_rework, is_valid_reject, repeat_breakdowns
from app.services.verification.format import plural

MIN_ORDERS = 5
COMPLEXITY = {Criticality.A: 1.5, Criticality.B: 1.2, Criticality.C: 1.0}

LABELS = {
    "quality": "Качество работ",
    "on_time": "Выполнение в срок",
    "no_returns": "Без возвратов и повторных поломок",
    "volume": "Объём с учётом сложности",
    "no_rejects": "Без отказов без причины",
}


@dataclass
class Component:
    key: str
    label: str
    weight: float
    value: float  # 0..1
    detail: str

    @property
    def points(self) -> float:
        return round(self.weight * self.value * 100, 1)

    @property
    def potential(self) -> float:
        """Сколько баллов рейтинга даст эта составляющая, если довести её до максимума."""
        return round(self.weight * (1 - self.value) * 100, 1)


@dataclass
class WorkerRating:
    employee: Employee
    orders: int
    score: float | None  # None — недостаточно данных
    components: list[Component] = field(default_factory=list)
    explanation: str = ""
    rank: int | None = None


@dataclass
class BrigadeRating:
    brigade: Brigade
    members: int
    orders: int
    score: float | None
    components: list[Component] = field(default_factory=list)


@dataclass
class RatingReport:
    start: datetime
    end: datetime
    workers: list[WorkerRating]
    brigades: list[BrigadeRating]


def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "—"


async def compute_ratings(
    session: AsyncSession, days: int = 30, now: datetime | None = None
) -> RatingReport:
    end = now or utcnow()
    start = end - timedelta(days=days)

    workers = list(
        await session.scalars(
            select(Employee).where(Employee.role == Role.WORKER, Employee.is_active.is_(True))
        )
    )
    closed = list(
        await session.scalars(
            select(Order)
            .where(
                Order.status == OrderStatus.CLOSED,
                Order.closed_at >= start,
                Order.closed_at < end,
                Order.assignee_id.is_not(None),
            )
            .options(selectinload(Order.events), selectinload(Order.equipment))
        )
    )
    unplanned = list(
        await session.scalars(
            select(Order).where(
                Order.type == OrderType.UNPLANNED,
                Order.created_at >= start - timedelta(days=60),
                Order.created_at < end + timedelta(days=7),
            )
        )
    )
    repeats = repeat_breakdowns(closed, unplanned)
    assessments = await latest_assessments(session, [o.id for o in closed])
    rejects = list(
        await session.scalars(
            select(OrderEvent).where(
                OrderEvent.action == "reject",
                OrderEvent.created_at >= start,
                OrderEvent.created_at < end,
            )
        )
    )

    by_worker: dict[int, list[Order]] = defaultdict(list)
    for order in closed:
        assert order.assignee_id is not None
        by_worker[order.assignee_id].append(order)

    unjustified: dict[int, int] = defaultdict(int)
    assigned: dict[int, int] = defaultdict(int)
    for event in rejects:
        if event.actor_id is None:
            continue
        assigned[event.actor_id] += 1
        if not is_valid_reject(event.reason):
            unjustified[event.actor_id] += 1

    volumes = {
        wid: sum(
            COMPLEXITY[o.equipment.criticality] * float(o.norm_hours or Decimal(1)) for o in orders
        )
        for wid, orders in by_worker.items()
    }
    best_volume = max(volumes.values(), default=0.0) or 1.0
    weights = settings.rating_weights

    ratings: list[WorkerRating] = []
    for worker in workers:
        orders = by_worker.get(worker.id, [])
        if len(orders) < MIN_ORDERS:
            ratings.append(
                WorkerRating(
                    employee=worker,
                    orders=len(orders),
                    score=None,
                    explanation=(
                        f"Недостаточно данных: закрыто {len(orders)} из {MIN_ORDERS} нарядов, "
                        f"нужных для рейтинга за {days} дн."
                    ),
                )
            )
            continue

        n = len(orders)
        scores = [
            a.final_score
            for o in orders
            if (a := assessments.get(o.id)) is not None and a.final_score is not None
        ]
        quality = sum(scores) / len(scores) / 100 if scores else 0.7
        on_time = sum(1 for o in orders if o.done_at and o.done_at <= o.deadline_at)
        returned = sum(1 for o in orders if had_rework(o) or o.id in repeats)
        volume = volumes.get(worker.id, 0.0)
        bad_rejects = unjustified.get(worker.id, 0)
        total_rejects = assigned.get(worker.id, 0)

        components = [
            Component(
                "quality", LABELS["quality"], weights["quality"], quality,
                f"Средняя оценка {round(quality * 100)} из 100 с учётом правок мастера "
                f"({len(scores)} {plural(len(scores), 'наряд', 'наряда', 'нарядов')})",
            ),
            Component(
                "on_time", LABELS["on_time"], weights["on_time"], on_time / n,
                f"В срок {on_time} из {n} ({_pct(on_time, n)})",
            ),
            Component(
                "no_returns", LABELS["no_returns"], weights["no_returns"], 1 - returned / n,
                f"Возвратов на доработку и повторных поломок за 7 дней: {returned} из {n} "
                f"({_pct(returned, n)})",
            ),
            Component(
                "volume", LABELS["volume"], weights["volume"], volume / best_volume,
                f"{round(volume)} нормо-часов с учётом критичности оборудования — "
                f"{_pct(round(volume), round(best_volume))} от лучшего за период",
            ),
            Component(
                "no_rejects", LABELS["no_rejects"], weights["no_rejects"],
                1 - min(1.0, bad_rejects / max(1, n + total_rejects)),
                f"Отказов без уважительной причины: {bad_rejects}"
                + (f" (всего отказов {total_rejects})" if total_rejects else ""),
            ),
        ]  # fmt: skip
        score = round(sum(c.weight * c.value for c in components) * 100, 1)
        ratings.append(
            WorkerRating(
                employee=worker,
                orders=n,
                score=score,
                components=components,
                explanation=explain(score, components, days),
            )
        )

    ranked = sorted((r for r in ratings if r.score is not None), key=lambda r: -(r.score or 0))
    for i, rating in enumerate(ranked, start=1):
        rating.rank = i
    ratings.sort(key=lambda r: (r.score is None, -(r.score or 0), r.employee.full_name))

    brigades = await _brigades(session, ratings)
    return RatingReport(start=start, end=end, workers=ratings, brigades=brigades)


def explain(score: float, components: list[Component], days: int) -> str:
    """Пояснение для исполнителя: сильная сторона и что поднимет рейтинг сильнее всего."""
    strongest = max(components, key=lambda c: c.value * c.weight)
    growth = max(components, key=lambda c: c.potential)
    lines = [f"Рейтинг {round(score)} из 100 за {days} дн."]
    lines.append(f"Сильная сторона — {strongest.label.lower()}: {strongest.detail.lower()}.")
    if growth.potential >= 1:
        lines.append(
            f"Больше всего поднимет — {growth.label.lower()}: {growth.detail.lower()}. "
            f"Если подтянуть эту часть до максимума, рейтинг вырастет на {round(growth.potential)} "
            f"{plural(round(growth.potential), 'балл', 'балла', 'баллов')}."
        )
    else:
        lines.append("Все составляющие близки к максимуму — так держать.")
    return " ".join(lines)


async def _brigades(session: AsyncSession, ratings: list[WorkerRating]) -> list[BrigadeRating]:
    brigades = {b.id: b for b in await session.scalars(select(Brigade))}
    grouped: dict[int, list[WorkerRating]] = defaultdict(list)
    for rating in ratings:
        if rating.employee.brigade_id is not None:
            grouped[rating.employee.brigade_id].append(rating)

    result = []
    for brigade_id, members in grouped.items():
        rated = [m for m in members if m.score is not None]
        orders = sum(m.orders for m in members)
        if not rated:
            result.append(BrigadeRating(brigades[brigade_id], len(members), orders, None))
            continue
        weight = sum(m.orders for m in rated)
        score = round(sum((m.score or 0) * m.orders for m in rated) / weight, 1)
        components = []
        for key, label in LABELS.items():
            parts = [(c, m.orders) for m in rated for c in m.components if c.key == key]
            value = sum(c.value * w for c, w in parts) / sum(w for _, w in parts)
            components.append(
                Component(
                    key,
                    label,
                    parts[0][0].weight,
                    value,
                    f"среднее по бригаде {round(value * 100)}%",
                )
            )
        result.append(BrigadeRating(brigades[brigade_id], len(members), orders, score, components))
    result.sort(key=lambda b: (b.score is None, -(b.score or 0)))
    return result
