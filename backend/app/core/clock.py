"""Ora si datele folosite de reguli.

In baza de date totul e in UTC. Orarul (08:00 - 22:00) si "luna" din regulament
sunt pe ora Romaniei, asa ca le calculam in Europe/Bucharest.
"""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Bucharest")


def now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """SQLite intoarce datele fara fus orar; le consideram UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def local_datetime(day: date, hour: time) -> datetime:
    """O ora din orarul local, transformata in UTC."""
    return datetime.combine(day, hour, tzinfo=LOCAL_TZ).astimezone(UTC)


def month_bounds(moment: datetime) -> tuple[datetime, datetime]:
    """Inceputul lunii (ora Romaniei) in care cade momentul si inceputul lunii urmatoare, in UTC."""
    local = as_utc(moment).astimezone(LOCAL_TZ)
    start = date(local.year, local.month, 1)
    end = date(local.year + 1, 1, 1) if local.month == 12 else date(local.year, local.month + 1, 1)
    return local_datetime(start, time()), local_datetime(end, time())
