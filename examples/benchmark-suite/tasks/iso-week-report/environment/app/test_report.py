from datetime import date

from labels import week_start
from report import weekly_report


def test_two_orders_in_one_week():
    rows = [(date(2024, 6, 10), 1200), (date(2024, 6, 14), 800)]
    expected = {"week": "2024-W24", "orders": 2, "total": 2000, "average": 1000}
    assert weekly_report(rows) == [expected]
    assert week_start("2024-W24") == date(2024, 6, 10)
