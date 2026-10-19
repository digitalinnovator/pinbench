#!/bin/bash
cat > /app/labels.py <<'EOF'
"""Week labels used by the sales reports."""

import re
from datetime import date

# [0-9], not \d: \d also matches digits outside ASCII.
_LABEL = re.compile(r"([0-9]{4})-W([0-9]{2})")


def week_label(day: date) -> str:
    """Return the ISO 8601 label of the week that contains `day`, for example '2024-W07'."""
    iso_year, iso_week, _ = day.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def week_start(label: str) -> date:
    """Return the Monday of the ISO week with this label, for example 2024-02-12 for '2024-W07'.

    Raises ValueError unless the label is exactly four ASCII digits, '-W' and two ASCII digits
    and names a week that the year has.
    """
    match = _LABEL.fullmatch(label)
    if match is None:
        raise ValueError(f"not a week label: {label!r}")
    # fromisocalendar raises ValueError for week 00 and for week 53 of a 52-week year.
    return date.fromisocalendar(int(match[1]), int(match[2]), 1)
EOF
cat > /app/report.py <<'EOF'
"""Weekly sales report."""

from datetime import date, timedelta

from labels import week_label

Row = tuple[date, int]


def _monday(day: date) -> date:
    """The Monday of the ISO week that contains `day`."""
    return day - timedelta(days=day.weekday())


def _nearest(numerator: int, denominator: int) -> int:
    """`numerator / denominator` to the nearest integer, halves towards positive infinity.

    Integer floor division keeps this right for a negative numerator. The denominator is
    positive.
    """
    return (2 * numerator + denominator) // (2 * denominator)


def _empty(monday: date) -> dict:
    return {"week": week_label(monday), "orders": 0, "total": 0, "average": 0}


def weekly_report(rows: list[Row], year: int | None = None) -> list[dict]:
    """Summarise sales rows as one entry per ISO week, oldest week first.

    `rows` holds `(day, amount)` pairs with the amount in cents. A negative amount is a
    refund: it lowers the total but is not an order. With `year`, only the rows whose week
    belongs to that ISO year are included. Every week from the oldest to the newest week with
    an included row is reported, the ones without rows as zeros.
    """
    weeks: dict[date, dict] = {}
    for day, amount in rows:
        if year is not None and day.isocalendar()[0] != year:
            continue
        monday = _monday(day)
        entry = weeks.setdefault(monday, _empty(monday))
        entry["total"] += amount
        if amount >= 0:
            entry["orders"] += 1
    if not weeks:
        return []
    report = []
    # Stepping the Monday by seven days crosses 52-week and 53-week years alike.
    monday, newest = min(weeks), max(weeks)
    while monday <= newest:
        entry = weeks.get(monday) or _empty(monday)
        if entry["orders"]:
            entry["average"] = _nearest(entry["total"], entry["orders"])
        report.append(entry)
        monday += timedelta(weeks=1)
    return report
EOF
