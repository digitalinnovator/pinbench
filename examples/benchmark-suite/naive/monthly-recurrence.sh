#!/bin/bash
# Careless solution. It covers every rule at first sight: the month arithmetic, the
# end-of-month rule, the weekend move with its comparison against `start`, and both string
# forms. What it gets wrong:
# - `start` is tested with isinstance(start, date) first. A datetime is also a date, so it is
#   never reduced to its date, and the weekend move then compares a date with a datetime;
# - the numbers of `period` are matched with \d+ and only their total is checked, so a part
#   of 0, a leading zero and a digit of another script all get through.
cat > /app/recurrence.py <<'EOF'
"""Monthly schedule dates."""

import calendar
import re
from datetime import date, datetime, timedelta


def next_month(d: date) -> date:
    """Return the same day in the month after `d`, or its last day if it has no such day."""
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _to_date(start: date | datetime | str) -> date:
    if isinstance(start, date):
        return start
    if isinstance(start, datetime):
        return start.date()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start):
        raise ValueError(f"invalid start: {start!r}")
    return date.fromisoformat(start)


def _to_months(period: str) -> int:
    match = re.fullmatch(r"(?:(\d+)y)?(?:(\d+)m)?", period)
    if not match:
        raise ValueError(f"invalid period: {period!r}")
    months = 12 * int(match.group(1) or 0) + int(match.group(2) or 0)
    if months < 1:
        raise ValueError(f"invalid period: {period!r}")
    return months


def _to_business_day(d: date, start: date) -> date:
    weekday = d.weekday()
    if weekday < 5:
        return d
    friday = d - timedelta(days=weekday - 4)
    if friday.month != d.month or friday < start:
        return d + timedelta(days=7 - weekday)
    return friday


def monthly_occurrences(
    start: date | datetime | str, count: int, period: str = "1m", business_days: bool = False
) -> list[date]:
    """Return `count` dates that are `period` apart, beginning with the month of `start`."""
    if count < 0:
        raise ValueError("count must not be negative")
    start = _to_date(start)
    step = _to_months(period)
    month_end = start.day == calendar.monthrange(start.year, start.month)[1]
    result = []
    for k in range(count):
        index = start.month - 1 + k * step
        year, month = start.year + index // 12, index % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        d = date(year, month, last_day if month_end else min(start.day, last_day))
        result.append(_to_business_day(d, start) if business_days else d)
    return result
EOF
