from durations import parse_duration


def test_minutes():
    assert parse_duration("30m") == 1800
