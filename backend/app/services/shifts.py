"""Границы смен: дневная 08:00–20:00, ночная 20:00–08:00 по времени предприятия."""

from datetime import UTC, datetime, time, timedelta

from app.config import settings
from app.models.base import utcnow
from app.models.enums import Shift


def shift_bounds(at: datetime | None = None) -> tuple[Shift, datetime, datetime]:
    """Смена, в которую попадает момент `at`, и её границы (в UTC)."""
    tz = settings.tz
    local = (at or utcnow()).astimezone(tz)
    day_start = datetime.combine(local.date(), time(settings.day_shift_start_hour), tz)
    night_start = datetime.combine(local.date(), time(settings.night_shift_start_hour), tz)

    if day_start <= local < night_start:
        shift, start, end = Shift.DAY, day_start, night_start
    else:
        start = night_start if local >= night_start else night_start - timedelta(days=1)
        shift, end = Shift.NIGHT, day_start + timedelta(days=1 if local >= night_start else 0)
    return shift, start.astimezone(UTC), end.astimezone(UTC)


def shift_of(at: datetime) -> Shift:
    return shift_bounds(at)[0]
