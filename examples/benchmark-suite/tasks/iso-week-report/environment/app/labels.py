"""Week labels used by the sales reports."""

from datetime import date, datetime


def week_label(day: date) -> str:
    """Return the label of the week that contains `day`, for example '2024-W07'."""
    return day.strftime("%Y-W%V")


def week_start(label: str) -> date:
    """Return the Monday of the week with this label, for example 2024-02-12 for '2024-W07'."""
    return datetime.strptime(label + "-1", "%Y-W%W-%w").date()
