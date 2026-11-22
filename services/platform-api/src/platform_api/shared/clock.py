"""Time. Handlers and jobs call `clock.utcnow()` through the module so a test can replace it."""

import calendar
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def add_months(start: datetime, months: int) -> datetime:
    """Same day of the month, or the last day of the month when it has no such day."""
    index = start.year * 12 + (start.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)
