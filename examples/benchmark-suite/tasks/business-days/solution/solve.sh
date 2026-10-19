#!/bin/bash
cat > /app/bizdays.py <<'EOF'
import re
from collections.abc import Iterable
from datetime import date, timedelta

_ONE_DAY = timedelta(days=1)
_ISO_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")


def _calendar_date(value: date | str) -> date:
    """Turn a date, a datetime or a `YYYY-MM-DD` string into a plain date."""
    if isinstance(value, date):  # a datetime is a date too: drop its time of day
        return date(value.year, value.month, value.day)
    if isinstance(value, str):
        match = _ISO_DATE.fullmatch(value)
        if match is None:
            raise ValueError(f"not a YYYY-MM-DD date: {value!r}")
        year, month, day = map(int, match.groups())
        return date(year, month, day)  # ValueError when the date does not exist
    raise TypeError(f"expected a date, a datetime or a str, got {type(value).__name__}")


def _is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def _shift(day: date, step: timedelta) -> date:
    """Move by one day. Leaving the range of `date` is a ValueError, not an OverflowError."""
    try:
        return day + step
    except OverflowError:
        raise ValueError("no such day between date.min and date.max") from None


def add_business_days(
    start: date | str,
    n: int,
    holidays: Iterable[date | str] = (),
    substitute: bool = False,
) -> date:
    """Return the date that lies `n` business days from `start`."""
    # Checked in the order start, n, holidays: the first invalid argument decides the error.
    current = _calendar_date(start)
    if type(n) is not int:  # rejects bool and every other subclass of int
        raise TypeError(f"n must be an int, got {type(n).__name__}")
    closed = set()
    for entry in holidays:
        closed.add(_calendar_date(entry))

    if substitute:
        # Every listed holiday is known before the first substitute is placed.
        for holiday in sorted(day for day in closed if _is_weekend(day)):
            try:
                day = holiday + _ONE_DAY
                while _is_weekend(day) or day in closed:
                    day += _ONE_DAY
            except OverflowError:
                continue  # no day is left after this holiday
            closed.add(day)

    def is_business_day(day: date) -> bool:
        return not _is_weekend(day) and day not in closed

    step = -_ONE_DAY if n < 0 else _ONE_DAY
    while not is_business_day(current):
        current = _shift(current, step)

    remaining = abs(n)
    while remaining:
        current = _shift(current, step)
        if is_business_day(current):
            remaining -= 1
    return current
EOF
