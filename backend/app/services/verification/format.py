"""Числа и длительности по-русски: «1 ч 40 мин», «1,5 л», «в 2,6 раза»."""

from decimal import Decimal


def num(value: Decimal | float, digits: int = 2) -> str:
    """1.50 → «1,5»; 6.000 → «6»."""
    text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def duration(minutes: float) -> str:
    hours, mins = divmod(abs(round(minutes)), 60)
    if hours and mins:
        return f"{hours} ч {mins} мин"
    if hours:
        return f"{hours} ч"
    return f"{mins} мин"


def times(ratio: float) -> str:
    """Во сколько раз: «в 2,6 раза»."""
    return f"в {num(ratio, 1)} раза"


def plural(n: int, one: str, few: str, many: str) -> str:
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 14:
        return many
    last = n_abs % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many
