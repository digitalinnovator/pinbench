import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, "/app")
from labels import week_label, week_start  # noqa: E402
from report import weekly_report  # noqa: E402


def counts(report):
    return [(entry["orders"], entry["total"]) for entry in report]


def labels(report):
    return [entry["week"] for entry in report]


def averages(report):
    return [entry["average"] for entry in report]


def one_week(*amounts):
    """Rows for the given amounts on consecutive days of 2024-W24 (it starts on 10 June)."""
    return [(date(2024, 6, 10 + i), amount) for i, amount in enumerate(amounts)]


def no_rows(label):
    return {"week": label, "orders": 0, "total": 0, "average": 0}


# --- week_label and week_start ------------------------------------------------------------


def test_label_is_iso_year_and_two_digit_iso_week():
    assert week_label(date(2024, 2, 14)) == "2024-W07"
    assert week_label(date(2020, 12, 31)) == "2020-W53"
    assert week_label(date(2024, 12, 30)) == "2025-W01"
    assert week_label(date(2021, 1, 1)) == "2020-W53"


def test_start_is_the_monday_of_the_week():
    assert week_start("2024-W07") == date(2024, 2, 12)
    assert week_start("2024-W52") == date(2024, 12, 23)
    assert week_start("2021-W01") == date(2021, 1, 4)
    # a week that begins in the year before
    assert week_start("2025-W01") == date(2024, 12, 30)
    assert week_start("2020-W01") == date(2019, 12, 30)
    # week 53
    assert week_start("2020-W53") == date(2020, 12, 28)
    assert week_start("2026-W53") == date(2026, 12, 28)
    # the label of any day leads back to the Monday of its week
    day = date(2019, 12, 20)
    while day <= date(2021, 1, 15):
        assert week_start(week_label(day)) == day - timedelta(days=day.weekday())
        day += timedelta(days=1)


@pytest.mark.parametrize(
    "label",
    [
        "2024-W7",  # the week number is two digits
        "2024-W07-1",  # nothing but the label
        "2024-W07\n",
        "2024-w07",  # "-W" with a capital W
        "2024-W+7",  # "+" is not a digit
        "２０２４-W07",  # full-width digits are not ASCII digits
        "2024-W０７",
        "٢٠٢٤-W٠٧",  # nor are Arabic-Indic digits
        "2024-W53",  # 2024 has 52 weeks
    ],
)
def test_start_rejects_a_string_that_is_not_a_valid_label(label):
    with pytest.raises(ValueError):
        week_start(label)


def test_start_rejects_other_shapes_and_week_numbers():
    others = ["", "24-W07", "12024-W07", "2020-W5", " 2024-W07", "2024-W07 ", "2024W07"]
    for label in [*others, "2024-07", "2024-W00", "2024-W54"]:
        with pytest.raises(ValueError):
            week_start(label)


# --- weekly_report: grouping, counting, ordering --------------------------------------------


def test_one_dict_per_week_and_a_week_runs_monday_to_sunday():
    rows = [(date(2024, 2, 12), 500), (date(2024, 2, 14), 250), (date(2024, 2, 18), 150)]
    assert weekly_report(rows) == [
        {"week": "2024-W07", "orders": 3, "total": 900, "average": 300}
    ]
    rows = [(date(2024, 6, 9), 100), (date(2024, 6, 10), 200), (date(2024, 6, 16), 300)]
    report = weekly_report(rows)
    assert labels(report) == ["2024-W23", "2024-W24"]
    assert counts(report) == [(1, 100), (2, 500)]


def test_oldest_week_first_for_any_input_order():
    rows = [
        (date(2024, 1, 10), 3),
        (date(2023, 12, 27), 1),
        (date(2024, 1, 3), 2),
        (date(2023, 12, 31), 10),
        (date(2024, 1, 1), 20),
    ]
    report = weekly_report(rows)
    assert labels(report) == ["2023-W52", "2024-W01", "2024-W02"]
    assert counts(report) == [(2, 11), (2, 22), (1, 3)]


def test_new_year_week_is_one_row_between_its_neighbours():
    rows = [(date(2024, 12, 30), 100), (date(2025, 1, 2), 250), (date(2025, 1, 5), 50)]
    assert weekly_report(rows) == [
        {"week": "2025-W01", "orders": 3, "total": 400, "average": 133}
    ]
    # week 53 of 2020 runs into January 2021
    report = weekly_report([(date(2021, 1, 3), 70), (date(2020, 12, 28), 30)])
    assert labels(report) == ["2020-W53"]
    assert counts(report) == [(2, 100)]
    rows = [(date(2025, 1, 6), 3), (date(2024, 12, 31), 2), (date(2024, 12, 27), 1)]
    report = weekly_report(rows)
    assert labels(report) == ["2024-W52", "2025-W01", "2025-W02"]
    assert counts(report) == [(1, 1), (1, 2), (1, 3)]
    rows = [(date(2021, 1, 6), 4), (date(2020, 12, 23), 1), (date(2020, 12, 30), 2)]
    report = weekly_report(rows)
    assert labels(report) == ["2020-W52", "2020-W53", "2021-W01"]
    assert counts(report) == [(1, 1), (1, 2), (1, 4)]


# --- weekly_report: the year argument -------------------------------------------------------

YEAR_ROWS = [(date(2023, 3, 8), 60), (date(2024, 3, 6), 40), (date(2024, 3, 13), 5)]


def test_year_includes_only_the_rows_whose_week_is_in_that_year():
    report = weekly_report(YEAR_ROWS, year=2024)
    assert labels(report) == ["2024-W10", "2024-W11"]
    assert counts(report) == [(1, 40), (1, 5)]
    assert weekly_report(YEAR_ROWS, 2023) == [
        {"week": "2023-W10", "orders": 1, "total": 60, "average": 60}
    ]
    # the year of the week, not of the day
    december = [(date(2024, 12, 27), 1), (date(2024, 12, 30), 2), (date(2025, 1, 2), 4)]
    assert counts(weekly_report(december, year=2025)) == [(2, 6)]
    assert counts(weekly_report(december, year=2024)) == [(1, 1)]
    january = [(date(2021, 1, 2), 8), (date(2021, 1, 5), 16)]
    assert counts(weekly_report(january, year=2020)) == [(1, 8)]
    assert counts(weekly_report(january, year=2021)) == [(1, 16)]


def test_no_included_rows_is_an_empty_list():
    assert weekly_report([]) == []
    assert weekly_report([], year=2024) == []
    assert weekly_report(YEAR_ROWS, year=2022) == []


# --- weekly_report: refunds -----------------------------------------------------------------


def test_refund_adds_to_total_but_is_not_an_order():
    report = weekly_report(one_week(1200, -300, 800))
    assert labels(report) == ["2024-W24"]
    assert counts(report) == [(2, 1700)]
    # a week with nothing but a refund
    rows = [(date(2024, 6, 19), -200), (date(2024, 6, 10), 500)]
    assert weekly_report(rows) == [
        {"week": "2024-W24", "orders": 1, "total": 500, "average": 500},
        {"week": "2024-W25", "orders": 0, "total": -200, "average": 0},
    ]
    # an amount of 0 is not negative
    assert counts(weekly_report(one_week(0, -5))) == [(1, -5)]
    assert counts(weekly_report(one_week(0, 0, 9))) == [(3, 9)]


# --- weekly_report: weeks in between without rows -------------------------------------------


def test_weeks_in_between_are_listed_with_zeros():
    rows = [(date(2024, 6, 26), 300), (date(2024, 6, 5), 100)]
    assert weekly_report(rows) == [
        {"week": "2024-W23", "orders": 1, "total": 100, "average": 100},
        no_rows("2024-W24"),
        no_rows("2024-W25"),
        {"week": "2024-W26", "orders": 1, "total": 300, "average": 300},
    ]


def test_weeks_in_between_across_the_end_of_a_52_week_year():
    report = weekly_report([(date(2024, 12, 18), 1), (date(2025, 1, 15), 2)])
    assert labels(report) == ["2024-W51", "2024-W52", "2025-W01", "2025-W02", "2025-W03"]
    assert counts(report) == [(1, 1), (0, 0), (0, 0), (0, 0), (1, 2)]
    assert averages(report) == [1, 0, 0, 0, 2]


def test_weeks_in_between_across_a_53_week_year():
    report = weekly_report([(date(2021, 1, 13), 2), (date(2020, 12, 16), 1)])
    assert labels(report) == ["2020-W51", "2020-W52", "2020-W53", "2021-W01", "2021-W02"]
    assert counts(report) == [(1, 1), (0, 0), (0, 0), (0, 0), (1, 2)]


def test_weeks_in_between_are_all_the_weeks_of_a_53_week_year():
    # from the last week of 2019 to the first of 2021: the 53 weeks of 2020 lie in between
    report = weekly_report([(date(2019, 12, 25), 5), (date(2021, 1, 6), 7)])
    weeks_of_2020 = [f"2020-W{number:02d}" for number in range(1, 54)]
    assert labels(report) == ["2019-W52", *weeks_of_2020, "2021-W01"]
    assert counts(report) == [(1, 5), *[(0, 0)] * 53, (1, 7)]


def test_weeks_in_between_with_the_year_argument():
    rows = [
        (date(2023, 12, 13), 9),
        (date(2024, 3, 6), 40),
        (date(2024, 3, 20), 5),
        (date(2025, 2, 5), 7),
    ]
    report = weekly_report(rows, year=2024)
    assert labels(report) == ["2024-W10", "2024-W11", "2024-W12"]
    assert counts(report) == [(1, 40), (0, 0), (1, 5)]
    rows = [(date(2024, 12, 11), 1), (date(2024, 12, 30), 2), (date(2025, 1, 15), 4)]
    assert labels(weekly_report(rows, year=2024)) == ["2024-W50"]
    report = weekly_report(rows, year=2025)
    assert labels(report) == ["2025-W01", "2025-W02", "2025-W03"]
    assert counts(report) == [(1, 2), (0, 0), (1, 4)]
    assert labels(weekly_report(rows)) == [
        "2024-W50",
        "2024-W51",
        "2024-W52",
        "2025-W01",
        "2025-W02",
        "2025-W03",
    ]


# --- weekly_report: the average -------------------------------------------------------------


def test_average_is_total_over_orders_to_the_nearest_cent():
    assert averages(weekly_report(one_week(1200, 800, 400))) == [800]
    assert averages(weekly_report(one_week(100, 100, 101))) == [100]
    assert averages(weekly_report(one_week(100, 101, 101))) == [101]
    # the total includes the refunds, the number of orders does not
    assert averages(weekly_report(one_week(1200, -300, 800))) == [850]


@pytest.mark.parametrize(
    ("amounts", "average"),
    [
        ((2, 3), 3),  # 2.5
        ((1200, -299, 800), 851),  # 850.5
        ((100, 200, -303), -1),  # -1.5
        ((500, 0, -505), -2),  # -2.5
        ((100, 100, 100, -308), -3),  # -2.67
        ((0, -5), -5),  # one order, a total of -5
    ],
)
def test_average_rounding(amounts, average):
    assert averages(weekly_report(one_week(*amounts))) == [average]
