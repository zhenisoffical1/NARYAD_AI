"""Отчёт как данные: заголовок, период, показатели, таблицы, текстовая сводка.

Одна структура — три вида: экран (JSON), Excel и PDF. Поэтому цифры в выгрузках всегда
совпадают с тем, что мастер видел на экране.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from app.config import settings
from app.errors import Invalid
from app.models.base import utcnow
from app.services.shifts import shift_bounds

Period = Literal["shift", "day", "week", "month", "custom"]
Align = Literal["left", "right"]


@dataclass
class Column:
    key: str
    title: str
    align: Align = "left"
    width: int = 14  # ширина в Excel, символов


@dataclass
class Table:
    title: str
    columns: list[Column]
    rows: list[dict[str, Any]]
    note: str | None = None  # пояснение под таблицей
    # Ключ колонки, по значению которой строка выделяется (например, «просрочен»)
    highlight: str | None = None


@dataclass
class Kpi:
    label: str
    value: str
    tone: Literal["default", "danger", "ok"] = "default"


@dataclass
class Report:
    kind: str
    title: str
    period_label: str
    generated_at: datetime
    kpis: list[Kpi] = field(default_factory=list)
    summary: str | None = None  # текст ИИ или шаблона
    summary_source: str | None = None  # llm | rules
    tables: list[Table] = field(default_factory=list)
    filters: str | None = None  # «Участок: Дробление»


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime
    label: str

    @property
    def days(self) -> int:
        return max(1, round((self.end - self.start).total_seconds() / 86400))


def _local(d: date, hour: int = 0) -> datetime:
    return datetime.combine(d, time(hour), settings.tz).astimezone(UTC)


def fmt_date(dt: datetime) -> str:
    return dt.astimezone(settings.tz).strftime("%d.%m.%Y")


def fmt_dt(dt: datetime | None) -> str:
    return dt.astimezone(settings.tz).strftime("%d.%m %H:%M") if dt else "—"


def window(period: Period, date_from: date | None = None, date_to: date | None = None) -> Window:
    """Границы периода в UTC и подпись для заголовка отчёта."""
    now = utcnow()
    today = now.astimezone(settings.tz).date()
    if period == "shift":
        shift, start, end = shift_bounds(now)
        name = "дневная" if shift.value == "day" else "ночная"
        return Window(start, end, f"Смена {name}, {fmt_dt(start)} — {fmt_dt(end)}")
    if period == "day":
        start = _local(today)
        return Window(start, start + timedelta(days=1), f"Сутки {fmt_date(start)}")
    if period == "week":
        start = _local(today - timedelta(days=6))
        return Window(start, _local(today + timedelta(days=1)),
                      f"Неделя {fmt_date(start)} — {today:%d.%m.%Y}")  # fmt: skip
    if period == "month":
        start = _local(today - timedelta(days=29))
        return Window(start, _local(today + timedelta(days=1)),
                      f"30 дней {fmt_date(start)} — {today:%d.%m.%Y}")  # fmt: skip
    if date_from is None or date_to is None:
        raise Invalid("Для своего периода укажите даты «с» и «по».")
    if date_to < date_from:
        raise Invalid("Дата «по» раньше даты «с». Поменяйте их местами.")
    if (date_to - date_from).days > 366:
        raise Invalid("Период длиннее года. Выберите период до 12 месяцев.")
    return Window(
        _local(date_from),
        _local(date_to + timedelta(days=1)),
        f"Период {date_from:%d.%m.%Y} — {date_to:%d.%m.%Y}",
    )
