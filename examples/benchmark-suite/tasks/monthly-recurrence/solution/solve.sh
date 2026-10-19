#!/bin/bash
cat > /app/recurrence.py <<'EOF'
"""Monthly schedule dates."""

import calendar
import re
from datetime import date, datetime, timedelta

# [0-9] and fullmatch, not \d and $: \d also matches digits of other scripts, and $ lets a
# trailing newline through.
_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_NUMBER = r"[1-9][0-9]*"  # 1 or more, no leading zeros
_PERIOD = re.compile(rf"(?:({_NUMBER})y)?(?:({_NUMBER})m)?")


def next_month(d: date) -> date:
    """Return the same day in the month after `d`, or its last day if it has no such day."""
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _as_date(start: date | datetime | str) -> date:
    """Return `start` as a plain date. A string must be exactly YYYY-MM-DD and a real date."""
    if isinstance(start, datetime):
        # Checked before anything else: a datetime is also a date, and it neither compares
        # with a plain date nor belongs in the result.
        return start.date()
    if not isinstance(start, str):
        return start
    match = _ISO_DATE.fullmatch(start)
    if match is None:
        # date.fromisoformat alone is too generous: it also takes 20240315 and 2024-W11-5.
        raise ValueError(f"not a date in the form YYYY-MM-DD: {start!r}")
    year, month, day = (int(part) for part in match.groups())
    return date(year, month, day)  # ValueError for a month or day that does not exist


def _as_months(period: str) -> int:
    """Return the number of months in a period such as 1y6m, 2y or 18m."""
    match = _PERIOD.fullmatch(period)
    if match is None or not period:  # both parts are optional, so "" matches the pattern
        raise ValueError(f"not a period: {period!r}")
    years, months = (int(part) if part else 0 for part in match.groups())
    return 12 * years + months


def _off_the_weekend(d: date, start: date) -> date:
    """Move a Saturday or Sunday to the Friday before, or to the Monday after it if that
    Friday is in the previous month or is earlier than `start`."""
    weekday = d.weekday()  # Monday is 0, Saturday 5, Sunday 6
    if weekday < 5:
        return d
    friday = d - timedelta(days=weekday - 4)
    if friday.month == d.month and friday >= start:
        return friday
    return d + timedelta(days=7 - weekday)


def monthly_occurrences(
    start: date | datetime | str, count: int, period: str = "1m", business_days: bool = False
) -> list[date]:
    """Return `count` dates that are `period` apart, beginning with the month of `start`."""
    # Every argument is checked before the loop, so a count of 0 does not hide a bad one.
    if count < 0:
        raise ValueError(f"count must not be negative: {count}")
    first = _as_date(start)
    step = _as_months(period)
    month_end = first.day == calendar.monthrange(first.year, first.month)[1]
    result = []
    for k in range(count):
        # Work from the start date every time: stepping from the previous date would keep
        # a day that a short month had shortened or a weekend had moved.
        years, month_index = divmod(first.month - 1 + k * step, 12)
        year, month = first.year + years, month_index + 1
        last_day = calendar.monthrange(year, month)[1]
        day = date(year, month, last_day if month_end else min(first.day, last_day))
        result.append(_off_the_weekend(day, first) if business_days else day)
    return result
EOF
