import sys

import pytest

sys.path.insert(0, "/app")
from numfmt import format_decimal  # noqa: E402


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [("1234.5", 2, "1,234.50"), ("-.5", 0, "-1"), ("-9876543.21", 1, "-9,876,543.2")],
)
def test_format(value, places, expected):
    assert format_decimal(value, places) == expected


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [("0.125", 2, "0.13"), ("2.4449", 2, "2.44"), ("-0.005", 2, "-0.01")],
)
def test_rounding(value, places, expected):
    assert format_decimal(value, places) == expected


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [("999999.995", 2, "1,000,000.00"), ("999.5", 0, "1,000")],
)
def test_carry(value, places, expected):
    assert format_decimal(value, places) == expected


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [(".5", 1, "0.5"), ("5.", 2, "5.00"), ("+1234.5", 1, "1,234.5"), ("007.25", 2, "7.25")],
)
def test_input_forms(value, places, expected):
    assert format_decimal(value, places) == expected


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [("-0.004", 2, "0.00"), ("-0.4", 0, "0")],
)
def test_sign_follows_rounded_result(value, places, expected):
    assert format_decimal(value, places) == expected


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        # 32 digits before the point.
        (
            "12345678901234567890123456789012.345",
            2,
            "12,345,678,901,234,567,890,123,456,789,012.35",
        ),
        # 40 digits before the point and 40 after it, rounded at 38 places.
        (
            "1234567890123456789012345678901234567890.0123456789012345678901234567890123456789",
            38,
            "1,234,567,890,123,456,789,012,345,678,901,234,567,890"
            ".01234567890123456789012345678901234568",
        ),
        # A short value with many places.
        ("2.5", 60, "2.5" + "0" * 59),
        # 150 nines on each side of the point: the carry runs through all of them.
        ("-" + "9" * 150 + "." + "9" * 150, 149, "-1" + ",000" * 50 + "." + "0" * 149),
    ],
    ids=["long-integer", "long-both", "many-places", "long-carry"],
)
def test_long_values_are_exact(value, places, expected):
    assert format_decimal(value, places) == expected


@pytest.mark.parametrize(
    "value",
    ["", ".", "+", "1.2.3", "1e3", "1_000", "1,234", "1 2", "\t12", "12 ", "12\n"],
)
def test_invalid_value(value):
    with pytest.raises(ValueError):
        format_decimal(value, 2)


def test_negative_places():
    with pytest.raises(ValueError):
        format_decimal("1.5", -1)
