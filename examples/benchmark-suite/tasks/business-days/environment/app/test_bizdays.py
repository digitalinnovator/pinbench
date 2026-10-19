from datetime import date

from bizdays import add_business_days


def test_skips_weekend_and_holiday():
    # 2024-03-04 is a Monday.
    assert add_business_days(date(2024, 3, 4), 3, []) == date(2024, 3, 7)
    assert add_business_days("2024-03-07", 2, ["2024-03-08"]) == date(2024, 3, 12)
