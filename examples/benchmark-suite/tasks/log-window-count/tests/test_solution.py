import sys

import pytest

sys.path.insert(0, "/app")
from logwindow import count_levels  # noqa: E402

# The whole of 1 March 2026 in UTC.
DAY = ("2026-03-01T00:00:00Z", "2026-03-02T00:00:00Z")


def test_counts_each_level():
    lines = [
        "2026-03-01T08:00:00Z INFO boot complete",
        "2026-03-01T08:00:01Z WARN disk at 91 percent",
        "2026-03-01T08:00:02Z INFO listening on 8080",
        "2026-03-01T08:00:03Z ERROR upstream refused connection",
        "2026-03-01T08:00:04Z INFO retry scheduled",
    ]
    result = count_levels(lines, *DAY)
    assert isinstance(result, dict)
    assert result == {"INFO": 3, "WARN": 1, "ERROR": 1}


def test_levels_without_a_counted_record_are_left_out():
    lines = [
        "2026-02-27T08:00:00Z ERROR too early",
        "2026-03-01T08:00:00Z INFO inside",
        "2026-03-05T08:00:00Z DEBUG too late",
    ]
    assert count_levels(lines, *DAY) == {"INFO": 1}
    assert count_levels(lines, "2026-03-02T00:00:00Z", "2026-03-03T00:00:00Z") == {}
    assert count_levels([], *DAY) == {}


def test_window_is_half_open():
    lines = [
        "2026-02-28T23:59:59Z DEBUG one second before the start",
        "2026-03-01T00:00:00Z INFO at the start",
        "2026-03-01T23:59:59Z WARN one second before the end",
        "2026-03-02T00:00:00Z ERROR at the end",
    ]
    assert count_levels(lines, *DAY) == {"INFO": 1, "WARN": 1}


def test_fractional_seconds():
    lines = [
        "2026-03-01T10:00:00.2Z DEBUG before the start",
        "2026-03-01T10:00:00.250Z INFO at the start",
        "2026-03-01T10:00:00.5Z INFO inside",
        "2026-03-01T10:00:00.749999Z WARN just before the end",
        "2026-03-01T10:00:00.750000Z ERROR at the end",
        "2026-03-01T10:00:01Z ERROR after the end",
    ]
    result = count_levels(lines, "2026-03-01T10:00:00.25Z", "2026-03-01T10:00:00.75Z")
    assert result == {"INFO": 2, "WARN": 1}


def test_offsets_are_compared_as_instants():
    cases = [
        ("2026-03-01T05:30:00+05:30", True),  # 00:00:00Z on 1 March, the start
        ("2026-02-28T20:00:00-05:00", True),  # 01:00:00Z on 1 March
        ("2026-03-01T01:30:00+02:00", False),  # 23:30:00Z on 28 February
        ("2026-03-01T19:00:00-05:00", False),  # 00:00:00Z on 2 March, the end
        ("2026-03-02T00:30:00+23:59", True),  # 00:31:00Z on 1 March
        ("2026-02-28T00:30:00-23:59", True),  # 00:29:00Z on 1 March
    ]
    for timestamp, counted in cases:
        result = count_levels([f"{timestamp} INFO sample"], *DAY)
        assert result == ({"INFO": 1} if counted else {}), timestamp


def test_bounds_with_offsets():
    # The window is 00:00Z to 04:00Z on 1 March.
    start, end = "2026-03-01T09:00:00+09:00", "2026-02-28T20:00:00-08:00"
    lines = [
        "2026-02-28T23:59:59Z DEBUG before the start",
        "2026-03-01T00:00:00Z INFO at the start",
        "2026-03-01T03:59:59Z WARN inside",
        "2026-03-01T04:00:00Z ERROR at the end",
    ]
    assert count_levels(lines, start, end) == {"INFO": 1, "WARN": 1}


def test_end_not_after_start_counts_nothing():
    lines = [
        "2026-03-01T09:30:00Z INFO between the two bounds",
        "2026-03-01T10:00:00Z INFO at the start",
    ]
    # An end one hour before the start, written with another offset, then an end equal to it.
    assert count_levels(lines, "2026-03-01T10:00:00Z", "2026-03-01T11:00:00+02:00") == {}
    assert count_levels(lines, "2026-03-01T10:00:00Z", "2026-03-01T10:00:00Z") == {}


def test_continuation_lines_are_counted_with_their_record():
    lines = [
        "(log rotated)",
        "  tail of an older record",
        "2026-03-01T10:00:00Z ERROR request failed",
        "Traceback (most recent call last):",
        '  File "app.py", line 12, in handle',
        "ValueError: ERROR code 7",
        "2026-03-01T10:00:01Z INFO recovered",
        "2026-03-01T10:00:02Z ERROR request failed again",
        "ValueError: ERROR code 9",
    ]
    assert count_levels(lines, *DAY) == {"ERROR": 6, "INFO": 1}


def test_empty_line_is_a_continuation_line():
    lines = [
        "2026-03-01T10:00:00Z INFO report follows",
        "",
        "2026-03-01T10:00:01Z WARN report was empty",
        "",
        "",
    ]
    assert count_levels(lines, *DAY) == {"INFO": 2, "WARN": 3}


def test_continuation_lines_of_a_record_outside_the_window_add_nothing():
    lines = [
        "2026-02-28T22:00:00Z ERROR nightly job failed",
        "Traceback (most recent call last):",
        "RuntimeError: exit status 3",
        "2026-03-01T10:00:00Z INFO job queued again",
        "2026-03-03T10:00:00Z WARN job is slow",
        "  attempt 1 of 3",
        "  attempt 2 of 3",
        "2026-03-01T11:00:00Z DEBUG job finished",
        "  payload follows",
        "2026-03-01T12:00:00Z ERROR job failed again",
    ]
    assert count_levels(lines, *DAY) == {"INFO": 1, "DEBUG": 2, "ERROR": 1}


def test_timestamp_that_is_not_at_the_start_of_the_line():
    lines = [
        "2026-03-01T10:00:00Z WARN replaying an event",
        "event: 2026-03-01T09:00:00Z ERROR original failure",
        "    2026-03-01T10:00:01Z ERROR child could not bind the port",
        "2026-03-01T10:00:02Z INFO child restarted",
    ]
    assert count_levels(lines, *DAY) == {"WARN": 3, "INFO": 1}


def test_line_that_does_not_begin_with_the_timestamp_form_is_a_continuation():
    for line in [
        "2026-03-01 10:00:01,123 ERROR handler failed",  # a space instead of the T
        "2026-03-01T10:00:01 ERROR job exited",  # no offset
        "2026-03-01T10:00:01.1234567Z ERROR job exited",  # seven digits after the point
    ]:
        lines = [
            "2026-03-01T10:00:00Z WARN worker output follows",
            line,
            "2026-03-01T10:00:02Z INFO worker restarted",
        ]
        assert count_levels(lines, *DAY) == {"WARN": 2, "INFO": 1}, line


@pytest.mark.parametrize(
    "timestamp",
    [
        pytest.param("2026-02-30T10:00:01Z", id="day-30-in-february"),
        pytest.param("2026-13-01T10:00:01Z", id="month-13"),
        pytest.param("2026-03-01T24:00:00Z", id="hour-24"),
        pytest.param("2026-03-01T10:60:00Z", id="minute-60"),
        pytest.param("2026-03-01T10:00:60Z", id="second-60"),
        pytest.param("2026-03-01T10:00:01+24:00", id="offset-hour-24"),
        pytest.param("2026-03-01T10:00:01+05:60", id="offset-minute-60"),
        pytest.param("2026-03-01T10:00:01-00:60", id="negative-offset-minute-60"),
    ],
)
def test_line_that_begins_with_an_invalid_timestamp_is_a_continuation(timestamp):
    lines = [
        "2026-03-01T10:00:00Z WARN imported rows follow",
        f"{timestamp} ERROR row rejected",
        "  reason: bad checksum",
        "2026-03-01T10:00:02Z INFO import finished",
    ]
    assert count_levels(lines, *DAY) == {"WARN": 3, "INFO": 1}


def test_day_29_in_february_exists_only_in_a_leap_year():
    lines = [
        "2024-02-29T12:00:00Z INFO leap day",
        "2026-02-29T12:00:00Z ERROR no such day in 2026",
    ]
    assert count_levels(lines, "2024-02-29T00:00:00Z", "2027-01-01T00:00:00Z") == {"INFO": 2}


def test_timestamp_not_followed_by_one_space_and_a_level_is_a_continuation():
    for line in [
        "2026-03-01T10:00:01Z",  # the timestamp alone
        "2026-03-01T10:00:01Z ",  # one space, then no level
        "2026-03-01T10:00:01Z  ERROR child failed",  # two spaces
        "2026-03-01T10:00:01Z\tERROR child failed",  # a tab
        "2026-03-01T10:00:01Z|ERROR|child failed",  # no space
    ]:
        lines = [
            "2026-03-01T10:00:00Z WARN child output follows",
            line,
            "2026-03-01T10:00:02Z INFO child restarted",
        ]
        assert count_levels(lines, *DAY) == {"WARN": 2, "INFO": 1}, repr(line)


def test_any_word_is_a_level_and_is_reported_as_written():
    lines = [
        "2026-03-01T10:00:00Z AUDIT user 7 logged in",
        "2026-03-01T10:00:01Z notice previous ERROR cleared",
        "2026-03-01T10:00:02Z Warn slow query",
        "2026-03-01T10:00:03Z WARN slow query",
        "2026-03-01T10:00:04Z AUDIT user 7 logged out",
        "2026-03-01T10:00:05Z DEBUG WARN threshold is 80",
        "2026-03-01T10:00:06Z HEARTBEAT",
    ]
    result = count_levels(lines, *DAY)
    expected = {"AUDIT": 2, "notice": 1, "Warn": 1, "WARN": 1, "DEBUG": 1, "HEARTBEAT": 1}
    assert result == expected


def test_records_in_any_time_order():
    lines = [
        "2026-03-01T12:00:00Z INFO inside",
        "2026-03-03T00:00:00Z ERROR after the window",
        "2026-03-01T06:00:00Z INFO inside and earlier than the first line",
        "2026-02-27T00:00:00Z ERROR before the window",
        "2026-03-01T18:00:00Z WARN inside",
    ]
    assert count_levels(lines, *DAY) == {"INFO": 2, "WARN": 1}


@pytest.mark.parametrize(
    "bound",
    [
        pytest.param("2026-03-01T00:00:00", id="no-offset"),
        pytest.param("2026-03-01 00:00:00Z", id="space-instead-of-T"),
        pytest.param("2026-03-01T00:00:00Z UTC", id="text-after-the-timestamp"),
        pytest.param("2026-03-01T00:00:00Z\n", id="newline-after-the-timestamp"),
        pytest.param("2026-02-30T00:00:00Z", id="day-30-in-february"),
        pytest.param("2026-03-01T00:00:00+05:60", id="offset-minute-60"),
    ],
)
def test_start_or_end_that_is_not_one_valid_timestamp_raises_value_error(bound):
    lines = ["2026-03-01T10:00:00Z INFO sample"]
    with pytest.raises(ValueError):
        count_levels(lines, bound, "2026-03-02T00:00:00Z")
    with pytest.raises(ValueError):
        count_levels(lines, "2026-02-01T00:00:00Z", bound)
