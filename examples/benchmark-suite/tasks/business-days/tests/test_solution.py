import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, "/app")
from bizdays import add_business_days  # noqa: E402


def mar(day):
    """A day in March 2024: the 4th is a Monday; the 9th/10th and 16th/17th are weekends."""
    return date(2024, 3, day)


class Count(int):
    """A subclass of int: its instances are ints, but not exactly of type int."""


@pytest.mark.parametrize(
    ("start", "n", "expected"),
    [
        (mar(13), -5, mar(6)),
        (mar(4), 260, date(2025, 3, 3)),
        # 9999-12-30 is a Thursday: the last day of the range can still be returned.
        (date(9999, 12, 30), 1, date.max),
    ],
    ids=["five-back", "a-year-forward", "up-to-date-max"],
)
def test_no_holidays(start, n, expected):
    assert add_business_days(start, n) == expected


@pytest.mark.parametrize(
    ("start", "n", "holidays", "expected"),
    [
        (mar(12), -1, {mar(8), mar(11)}, mar(7)),
        # Weekend holidays and repeats, and no substitute days without `substitute`.
        (mar(8), 2, [mar(9), mar(10), mar(9), mar(12), mar(12)], mar(13)),
    ],
    ids=["set", "weekend-and-repeats"],
)
def test_holidays_are_not_business_days(start, n, holidays, expected):
    assert add_business_days(start, n, holidays) == expected


def test_holidays_from_a_generator():
    holidays = (mar(day) for day in (5, 7))
    assert add_business_days(mar(4), 3, holidays) == mar(11)


@pytest.mark.parametrize(
    ("start", "n", "holidays", "expected"),
    [
        (mar(8), 0, [mar(8), mar(11)], mar(12)),
        (mar(16), -1, [mar(14), mar(15)], mar(12)),
    ],
    ids=["zero-rolls-forward", "negative-rolls-back"],
)
def test_start_is_not_a_business_day(start, n, holidays, expected):
    assert add_business_days(start, n, holidays) == expected


def test_datetime_start_uses_its_calendar_date_and_returns_a_date():
    on_a_monday = add_business_days(datetime(2024, 3, 4, 15, 30), 0)
    assert type(on_a_monday) is date
    assert on_a_monday == mar(4)
    on_a_saturday = add_business_days(datetime(2024, 3, 9, 23, 59), 0)
    assert type(on_a_saturday) is date
    assert on_a_saturday == mar(11)


def test_string_start_and_mixed_forms_of_holiday():
    holidays = ["2024-03-05", mar(6), datetime(2024, 3, 7, 12, 0), "2024-03-06"]
    result = add_business_days("2024-03-04", 1, holidays)
    assert type(result) is date
    assert result == mar(8)


@pytest.mark.parametrize(
    "text",
    [
        "20240305",
        "2024-3-5",
        "2024-03-05\n",
        "2024-W10-1",
        "2024-03- 5",
        "2024-02-30",
    ],
    ids=["compact", "unpadded", "trailing-newline", "week-form", "space-in-day", "no-such-day"],
)
def test_strings_that_are_not_a_yyyy_mm_dd_date_are_rejected(text):
    with pytest.raises(ValueError):
        add_business_days(mar(4), 1, [text])
    with pytest.raises(ValueError):
        add_business_days(text, 1, [])


@pytest.mark.parametrize("n", [True, Count(2)], ids=["bool", "int-subclass"])
def test_n_must_be_exactly_an_int(n):
    with pytest.raises(TypeError):
        add_business_days(mar(4), n, [])


def test_values_of_another_type_are_rejected():
    with pytest.raises(TypeError):
        add_business_days(mar(4), 1, [mar(5), None])
    with pytest.raises(TypeError):
        add_business_days(20240304, 1, [])
    with pytest.raises(TypeError):
        add_business_days(mar(4), 2.0, [])
    with pytest.raises(TypeError):
        add_business_days(mar(4), "2", [])


@pytest.mark.parametrize(
    ("start", "n", "holidays", "error"),
    [
        # `start` is checked before `n`.
        ("2024-02-30", True, [], ValueError),
        # `n` is checked before `holidays`.
        (mar(4), 2.5, ["2024-3-5"], TypeError),
    ],
    ids=["start-before-n", "n-before-holidays"],
)
def test_the_first_invalid_argument_decides_the_error(start, n, holidays, error):
    with pytest.raises(error):
        add_business_days(start, n, holidays)


def test_holiday_entries_are_checked_in_iteration_order():
    with pytest.raises(TypeError):
        add_business_days(mar(4), 1, [None, "2024-02-30"])
    with pytest.raises(ValueError):
        add_business_days(mar(4), 1, ["2024-02-30", None])


def test_day_to_return_outside_the_range_of_date():
    # date.max is a Friday and date.min is a Monday.
    with pytest.raises(ValueError):
        add_business_days(date.max, 1)
    with pytest.raises(ValueError):
        add_business_days(date.min, -1)


def test_starting_point_outside_the_range_of_date():
    with pytest.raises(ValueError):
        add_business_days(date.max, 0, [date.max])
    with pytest.raises(ValueError):
        add_business_days(date.min, -1, [date.min])


@pytest.mark.parametrize(
    ("start", "n", "holidays", "expected"),
    [
        # Saturday and Sunday: the substitutes are Monday and Tuesday.
        (mar(8), 1, [mar(9), mar(10)], mar(13)),
        # Monday is a holiday itself, listed after the Saturday: the substitute is Tuesday.
        (mar(8), 1, [mar(9), mar(11)], mar(13)),
        # Sunday, with Monday and Tuesday holidays themselves: the substitute is Wednesday.
        (mar(8), 1, [mar(10), mar(11), mar(12)], mar(14)),
        # One Saturday given three times: one substitute, the Monday.
        (mar(8), 1, [mar(9), datetime(2024, 3, 9, 10, 0), "2024-03-09"], mar(12)),
        # The start is the substitute of the Sunday, so it is not a business day.
        (mar(11), -1, [mar(10)], mar(7)),
        # Counting backwards over the two substitutes of a Saturday and Sunday.
        (mar(13), -1, [mar(9), mar(10)], mar(8)),
    ],
    ids=[
        "saturday-and-sunday",
        "monday-is-a-holiday",
        "monday-and-tuesday-are-holidays",
        "one-saturday-three-times",
        "start-is-a-substitute",
        "backwards-over-two-substitutes",
    ],
)
def test_substitute_days(start, n, holidays, expected):
    assert add_business_days(start, n, holidays, substitute=True) == expected
