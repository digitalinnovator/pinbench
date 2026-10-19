"""Weekly sales report."""

from datetime import date

from labels import week_label

Row = tuple[date, int]


def _week_key(day: date) -> tuple[int, int]:
    """Sort key of the week that contains `day`."""
    return day.year, day.isocalendar()[1]


def weekly_report(rows: list[Row], year: int | None = None) -> list[dict]:
    """Summarise sales rows as one entry per week, oldest week first.

    `rows` holds `(day, amount)` pairs with the amount in cents. With `year`, only the
    weeks of that year are reported.
    """
    weeks: dict[tuple[int, int], dict] = {}
    for day, amount in rows:
        if year is not None and day.year != year:
            continue
        entry = weeks.setdefault(
            _week_key(day), {"week": week_label(day), "orders": 0, "total": 0, "average": 0}
        )
        entry["orders"] += 1
        entry["total"] += amount
    for entry in weeks.values():
        entry["average"] = round(entry["total"] / entry["orders"])
    return [weeks[key] for key in sorted(weeks)]
