import sys

import pytest

sys.path.insert(0, "/app")
from durations import parse_duration  # noqa: E402


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("2h", 7200), ("1h30m", 5400), ("90s", 90), ("1h0m5s", 3605), ("0s", 0), ("10m15s", 615)],
)
def test_valid(text, seconds):
    assert parse_duration(text) == seconds


@pytest.mark.parametrize(
    "text", ["", "h", "10", "5d", "30m1h", "1h1h", "1h 30m", "-5s", "1.5h", "m30"]
)
def test_invalid(text):
    with pytest.raises(ValueError):
        parse_duration(text)


def test_returns_int():
    assert isinstance(parse_duration("1m"), int)
