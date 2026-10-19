"""Monthly schedule dates."""

import calendar
from datetime import date, datetime


def next_month(d: date) -> date:
    """Return the same day in the month after `d`, or its last day if it has no such day."""
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def monthly_occurrences(
    start: date | datetime | str, count: int, period: str = "1m", business_days: bool = False
) -> list[date]:
    """Return `count` dates that are `period` apart, beginning with the month of `start`."""
    raise NotImplementedError
