#!/bin/bash
cat > /app/bizdays.py <<'EOF'
from collections.abc import Iterable
from datetime import date, datetime, timedelta

ONE_DAY = timedelta(days=1)


def _to_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        if len(value) != 10:
            raise ValueError(f"expected YYYY-MM-DD, got {value!r}")
        return date.fromisoformat(value)
    raise TypeError("expected a date, a datetime or a str")


def add_business_days(
    start: date | str,
    n: int,
    holidays: Iterable[date | str] = (),
    substitute: bool = False,
) -> date:
    """Return the date that lies `n` business days from `start`."""
    if type(n) is not int:
        raise TypeError("n must be an int")
    current = _to_date(start)
    closed = {_to_date(h) for h in holidays}
    if substitute:
        for holiday in sorted(closed):
            if holiday.weekday() >= 5:
                day = holiday + ONE_DAY
                while day.weekday() >= 5 or day in closed:
                    day += ONE_DAY
                closed.add(day)

    def is_business_day(day: date) -> bool:
        return day.weekday() < 5 and day not in closed

    step = ONE_DAY if n >= 0 else -ONE_DAY
    try:
        while not is_business_day(current):
            current += step
        remaining = abs(n)
        while remaining:
            current += step
            if is_business_day(current):
                remaining -= 1
    except OverflowError:
        raise ValueError("no such day between date.min and date.max") from None
    return current
EOF
