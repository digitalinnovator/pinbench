import pytest

from numfmt import format_decimal


def test_format_decimal():
    assert format_decimal("1234567.891", 2) == "1,234,567.89"
    assert format_decimal("-42", 1) == "-42.0"
    with pytest.raises(ValueError):
        format_decimal("12a", 2)
