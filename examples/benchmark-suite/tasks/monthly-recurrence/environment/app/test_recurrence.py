from datetime import date

from recurrence import monthly_occurrences, next_month


def test_next_month():
    assert next_month(date(2023, 12, 15)) == date(2024, 1, 15)


def test_mid_month():
    expected = [date(2024, 3, 15), date(2024, 4, 15), date(2024, 5, 15)]
    assert monthly_occurrences(date(2024, 3, 15), 3) == expected
