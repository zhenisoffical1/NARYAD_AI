"""Общие правила качества: что считается возвратом и повторной поломкой.

Одна и та же логика нужна рейтингу, отчётам и аналитике — поэтому она здесь.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import timedelta

from app.models import Order
from app.models.enums import OrderStatus, OrderType

REPEAT_WINDOW = timedelta(days=7)

# Отказ с такой причиной — уважительный; остальное считается «без уважительной причины»
VALID_REJECT_REASONS = (
    "нет материалов",
    "нет допуска",
    "занят аварийным",
    "ждёт запчасти",
    "ждёт остановки оборудования",
    "болен",
    "не моя специальность",
)


def is_valid_reject(reason: str | None) -> bool:
    text = (reason or "").strip().lower()
    return any(text.startswith(valid) for valid in VALID_REJECT_REASONS)


def chronic_pairs(orders: Iterable[Order]) -> set[tuple[int, int]]:
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


def had_rework(order: Order) -> bool:
    return any(e.to_status == OrderStatus.REWORK for e in order.events)


def repeat_breakdowns(closed: Sequence[Order], all_unplanned: Sequence[Order]) -> dict[int, Order]:
    """id закрытого наряда → наряд с той же поломкой на том же оборудовании в течение 7 дней.

    Хронические пары (оборудование + шифр) не учитываются: это не вина исполнителя.
    """
    chronic = chronic_pairs(all_unplanned)
    by_equipment: dict[int, list[Order]] = defaultdict(list)
    for o in all_unplanned:
        by_equipment[o.equipment_id].append(o)

    result: dict[int, Order] = {}
    for order in closed:
        if (
            order.type != OrderType.UNPLANNED
            or order.done_at is None
            or (order.equipment_id, order.fault_code_id) in chronic
        ):
            continue
        window_end = order.done_at + REPEAT_WINDOW
        for later in by_equipment[order.equipment_id]:
            if (
                later.id != order.id
                and later.fault_code_id == order.fault_code_id
                and order.done_at < later.created_at <= window_end
            ):
                result[order.id] = later
                break
    return result
