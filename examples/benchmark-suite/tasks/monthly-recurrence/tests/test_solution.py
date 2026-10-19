import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, "/app")
from recurrence import monthly_occurrences, next_month  # noqa: E402


def d(text):
    return date.fromisoformat(text)


def rejects(*args, **kwargs):
    """True if the call raises ValueError. Any other exception fails the test."""
    try:
        monthly_occurrences(*args, **kwargs)
    except ValueError:
        return True
    return False


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        # The 30th is not the last day of March or January: the day number comes from `start`.
        ("2023-03-30", ["2023-03-30", "2023-04-30", "2023-05-30", "2023-06-30"]),
        ("2024-01-30", ["2024-01-30", "2024-02-29", "2024-03-30"]),
    ],
)
def test_schedule(start, expected):
    assert monthly_occurrences(d(start), len(expected)) == [d(e) for e in expected]


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        # `start` is the last day of its month, so every date is the last day of its month.
        ("2023-04-30", ["2023-04-30", "2023-05-31", "2023-06-30", "2023-07-31"]),
        ("2023-02-28", ["2023-02-28", "2023-03-31", "2023-04-30"]),
    ],
)
def test_start_on_the_last_day_of_its_month(start, expected):
    assert monthly_occurrences(d(start), len(expected)) == [d(e) for e in expected]


def test_leap_years():
    dates = monthly_occurrences(d("2024-02-29"), 49)
    assert len(dates) == 49
    assert dates[0] == d("2024-02-29")
    assert dates[1] == d("2024-03-31")
    assert dates[12] == d("2025-02-28")
    assert dates[13] == d("2025-03-31")
    assert dates[48] == d("2028-02-29")
    # February 2024 has 29 days, so the 28th is not its last day.
    expected = [d("2024-02-28"), d("2024-03-28"), d("2024-04-28")]
    assert monthly_occurrences(d("2024-02-28"), 3) == expected
    # 2100 is not a leap year.
    expected = [d("2100-01-30"), d("2100-02-28"), d("2100-03-30")]
    assert monthly_occurrences(d("2100-01-30"), 3) == expected


APRIL_15_BUSINESS_DAYS = [
    # Saturday 15 June and Sunday 15 September move to the Friday before.
    "2024-04-15",
    "2024-05-15",
    "2024-06-14",
    "2024-07-15",
    "2024-08-15",
    "2024-09-13",
    "2024-10-15",
]


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        ("2024-04-15", APRIL_15_BUSINESS_DAYS),
        # Saturday 1 June and Sunday 1 September: the Friday before is in the previous month.
        ("2024-05-01", ["2024-05-01", "2024-06-03", "2024-07-01", "2024-08-01", "2024-09-02"]),
        # Last days of the month: Saturday 31 January, Saturday 28 February, Tuesday 31 March.
        ("2025-12-31", ["2025-12-31", "2026-01-30", "2026-02-27", "2026-03-31"]),
    ],
)
def test_business_days(start, expected):
    dates = monthly_occurrences(d(start), len(expected), business_days=True)
    assert dates == [d(e) for e in expected]


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        # `start` is a Saturday: Friday 14 June is earlier than `start`, so Monday 17 June.
        ("2024-06-15", ["2024-06-17", "2024-07-15", "2024-08-15"]),
        # `start` is Saturday 31 August: the Monday after it is 2 September. The later dates
        # are not changed by that move; Saturday 30 November moves to Friday 29 November.
        ("2024-08-31", ["2024-09-02", "2024-09-30", "2024-10-31", "2024-11-29"]),
    ],
)
def test_business_day_is_never_earlier_than_start(start, expected):
    dates = monthly_occurrences(d(start), len(expected), business_days=True)
    assert dates == [d(e) for e in expected]


def test_count():
    assert monthly_occurrences(d("2024-10-31"), 0) == []
    dates = monthly_occurrences(d("2024-10-31"), 1)
    assert dates == [d("2024-10-31")]
    assert isinstance(dates, list)
    assert all(type(x) is date for x in dates)
    for count in (-1, -12):
        with pytest.raises(ValueError):
            monthly_occurrences(d("2024-03-15"), count)


def test_next_month_is_unchanged():
    assert next_month(d("2023-12-15")) == d("2024-01-15")
    assert next_month(d("2024-01-31")) == d("2024-02-29")
    assert next_month(d("2023-04-30")) == d("2023-05-30")


def test_string_start():
    dates = monthly_occurrences("2024-01-31", 3)
    assert dates == [d("2024-01-31"), d("2024-02-29"), d("2024-03-31")]
    assert all(type(x) is date for x in dates)
    # Saturday 1 June and Sunday 1 September stay where they are without business days.
    expected = [d("2024-06-01"), d("2024-07-01"), d("2024-08-01"), d("2024-09-01")]
    assert monthly_occurrences("2024-06-01", 4, business_days=False) == expected
    # `start` is a Sunday: Friday 14 June is earlier than `start`.
    moved = monthly_occurrences("2024-06-16", 3, business_days=True)
    assert moved == [d("2024-06-17"), d("2024-07-16"), d("2024-08-16")]


@pytest.mark.parametrize(
    "text",
    [
        "20240315",  # no dashes
        "2024-3-15",  # one-digit month
        "2024-03-15\n",  # something after the date
        "2024-02-30",  # the right form, but not a real date
    ],
)
def test_string_start_in_any_other_form_is_an_error(text):
    with pytest.raises(ValueError):
        monthly_occurrences(text, 3)


@pytest.mark.parametrize(
    ("start", "period", "expected"),
    [
        # `start` is the last day of its month.
        ("2024-01-31", "3m", ["2024-01-31", "2024-04-30", "2024-07-31", "2024-10-31"]),
        ("2024-02-29", "1y", ["2024-02-29", "2025-02-28", "2026-02-28", "2027-02-28"]),
        # February has no 30th; August has one again.
        ("2023-08-30", "6m", ["2023-08-30", "2024-02-29", "2024-08-30", "2025-02-28"]),
    ],
)
def test_period(start, period, expected):
    dates = monthly_occurrences(d(start), len(expected), period=period)
    assert dates == [d(e) for e in expected]


def test_period_in_years_and_months():
    expected = [d("2023-11-30"), d("2025-05-31"), d("2026-11-30"), d("2028-05-31")]
    assert monthly_occurrences(d("2023-11-30"), 4, period="1y6m") == expected
    assert monthly_occurrences(d("2023-11-30"), 4, period="18m") == expected
    expected = [d("2024-03-31"), d("2025-01-31"), d("2025-11-30"), d("2026-09-30")]
    assert monthly_occurrences(d("2024-03-31"), 4, period="10m") == expected
    yearly = monthly_occurrences(d("2024-05-20"), 3, period="1y")
    assert yearly == [d("2024-05-20"), d("2025-05-20"), d("2026-05-20")]
    assert monthly_occurrences(d("2024-05-20"), 3, period="12m") == yearly


def test_period_with_business_days():
    # Saturday 31 August is `start`, Saturday 30 November and Saturday 31 May move to Friday.
    dates = monthly_occurrences(d("2024-08-31"), 4, period="3m", business_days=True)
    assert dates == [d("2024-09-02"), d("2024-11-29"), d("2025-02-28"), d("2025-05-30")]


def test_period_number_is_one_or_more():
    for text in ("0m", "0y", "1y0m", "0y6m"):
        assert rejects(d("2024-03-15"), 3, period=text), text


def test_period_number_has_no_leading_zeros():
    for text in ("06m", "01y", "1y06m", "012m"):
        assert rejects(d("2024-03-15"), 3, period=text), text


def test_period_in_any_other_shape_is_an_error():
    shapes = ("", "m", "y", "6", "1y6", "6m1y", "1y1y", "1.5y", "+6m", "-6m", "1_0m", "6d")
    for text in shapes:
        assert rejects(d("2024-03-15"), 3, period=text), repr(text)


def test_period_with_anything_else_is_an_error():
    for text in (" 6m", "6m ", "6 m", "1y 6m", "6m\n", "6M", "1Y", "1Y6M"):
        assert rejects(d("2024-03-15"), 3, period=text), repr(text)


def test_a_digit_is_one_of_0_to_9():
    # Digits of other scripts: Arabic-Indic three and five, full-width two.
    for text in ("٣m", "1٣m", "２y"):
        assert rejects(d("2024-03-15"), 3, period=text), ascii(text)
    for text in ("٢٠٢٤-٠٣-١٥", "2024-03-1٥"):
        assert rejects(text, 3), ascii(text)


def test_datetime_start():
    dates = monthly_occurrences(datetime(2024, 1, 31, 18, 45), 3)
    assert dates == [d("2024-01-31"), d("2024-02-29"), d("2024-03-31")]
    assert all(type(x) is date for x in dates)


def test_datetime_start_with_business_days():
    dates = monthly_occurrences(datetime(2024, 4, 15, 9, 30), 7, business_days=True)
    assert dates == [d(e) for e in APRIL_15_BUSINESS_DAYS]
    assert all(type(x) is date for x in dates)
    # `start` is a Saturday: Friday 14 June is earlier than it.
    moved = monthly_occurrences(datetime(2024, 6, 15, 23, 59), 3, business_days=True)
    assert moved == [d("2024-06-17"), d("2024-07-15"), d("2024-08-15")]
    assert all(type(x) is date for x in moved)


def test_count_zero_with_an_invalid_argument():
    assert monthly_occurrences("2024-03-15", 0, period="2y") == []
    assert rejects("2024-02-30", 0)
    assert rejects("not a date", 0)
    assert rejects(d("2024-03-15"), 0, period="")
    assert rejects(d("2024-03-15"), 0, period="6")
