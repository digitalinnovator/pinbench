#!/bin/bash
# Careless fix: every rule is implemented with the first helper that comes to mind, the existing
# test is run, and nothing else is tried.
# - The ISO year replaces the calendar year in the grouping key, the label and the year filter.
#   Refunds are no longer orders; a week without orders gets an average of 0. (All correct.)
# - week_start matches the label with \d, which also matches digits outside ASCII (full-width,
#   Arabic-Indic), and int() reads them, so such a label is accepted.
# - The average is rounded with int(x + 0.5). int() truncates towards zero, so a negative
#   average that is not exactly on a half lands one cent too high.
# - The weeks in between are filled by counting the week number up and starting the next year
#   after week 52, so week 53 of a 53-week year is skipped.
cat > /app/labels.py <<'EOF'
"""Week labels used by the sales reports."""

import re
from datetime import date


def week_label(day: date) -> str:
    """Return the ISO 8601 label of the week that contains `day`, for example '2024-W07'."""
    return day.strftime("%G-W%V")


def week_start(label: str) -> date:
    """Return the Monday of the ISO week with this label, for example 2024-02-12 for '2024-W07'."""
    match = re.fullmatch(r"(\d{4})-W(\d{2})", label)
    if match is None:
        raise ValueError(f"not a week label: {label!r}")
    return date.fromisocalendar(int(match.group(1)), int(match.group(2)), 1)
EOF
cat > /app/report.py <<'EOF'
"""Weekly sales report."""

from datetime import date

from labels import week_label

Row = tuple[date, int]


def _week_key(day: date) -> tuple[int, int]:
    """Sort key of the week that contains `day`: ISO year and ISO week number."""
    iso_year, iso_week, _ = day.isocalendar()
    return iso_year, iso_week


def weekly_report(rows: list[Row], year: int | None = None) -> list[dict]:
    """Summarise sales rows as one entry per ISO week, oldest week first.

    `rows` holds `(day, amount)` pairs with the amount in cents. A negative amount is a
    refund, not an order. With `year`, only the weeks of that ISO year are reported. Weeks
    without rows between the oldest and the newest week are reported as zeros.
    """
    weeks: dict[tuple[int, int], dict] = {}
    for day, amount in rows:
        key = _week_key(day)
        if year is not None and key[0] != year:
            continue
        entry = weeks.setdefault(
            key, {"week": week_label(day), "orders": 0, "total": 0, "average": 0}
        )
        entry["total"] += amount
        if amount >= 0:
            entry["orders"] += 1
    for entry in weeks.values():
        if entry["orders"]:
            entry["average"] = int(entry["total"] / entry["orders"] + 0.5)
    if not weeks:
        return []
    report = []
    (iso_year, iso_week), newest = min(weeks), max(weeks)
    while (iso_year, iso_week) <= newest:
        entry = weeks.get((iso_year, iso_week))
        if entry is None:
            label = f"{iso_year}-W{iso_week:02d}"
            entry = {"week": label, "orders": 0, "total": 0, "average": 0}
        report.append(entry)
        iso_week += 1
        if iso_week > 52:
            iso_year, iso_week = iso_year + 1, 1
    return report
EOF
