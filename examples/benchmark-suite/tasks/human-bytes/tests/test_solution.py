import sys

import pytest

sys.path.insert(0, "/app")
import sizes  # noqa: E402


@pytest.mark.parametrize(("n", "text"), [(0, "0 B"), (1023, "1023 B")])
def test_below_1024_is_exact_integer(n, text):
    assert sizes.format_size(n) == text


@pytest.mark.parametrize(
    ("n", "text"),
    [
        (1024, "1.0 KiB"),
        (1500000000, "1.4 GiB"),  # 1.3969...
        (1280, "1.3 KiB"),  # exactly 1.25: halfway rounds up
    ],
)
def test_one_decimal_place_rounded_to_nearest_with_halves_up(n, text):
    assert sizes.format_size(n) == text


@pytest.mark.parametrize(
    ("n", "text"),
    [
        (1048524, "1023.9 KiB"),  # 1023.949... KiB
        (1048525, "1.0 MiB"),  # 1023.950... KiB would show 1024.0
        (1024**4 - 1, "1.0 TiB"),  # 1023.99... GiB would show 1024.0
        (1024**5 - 1, "1024.0 TiB"),  # TiB has no upper limit
    ],
)
def test_smallest_unit_whose_rounded_number_is_below_1024(n, text):
    assert sizes.format_size(n) == text


def test_format_is_exact_for_any_size_of_n():
    # 10**40 / 2**40 == 5**40, and 2**38 bytes is a quarter of a TiB: exactly ...625.25
    assert sizes.format_size(10**40 + 2**38) == "9094947017729282379150390625.3 TiB"


def test_negative_raises():
    with pytest.raises(ValueError):
        sizes.format_size(-1)


@pytest.mark.parametrize(
    ("text", "n"),
    [
        ("0 B", 0),
        ("9007199254740993 B", 2**53 + 1),
        ("0.9 KiB", 921),  # 921.6 rounded down
        ("117.7 MiB", 123417395),  # 123417395.2 rounded down
        ("9094947017729282379150390625.3 GiB", 9765625000000000000000000000322122547),  # ...547.2
        ("2048.3 TiB", 2252129667173580),  # 20483 * 2**40 / 10 == ...580.8 rounded down
    ],
)
def test_parse_is_the_exact_product_rounded_down(text, n):
    assert sizes.parse_size(text) == n


@pytest.mark.parametrize(
    "text",
    [
        "1.5 KiB\n",  # a character after the unit
        " 1.5 KiB",  # a character before the number
        "1.5\tKiB",  # a tab is not the single space
        "1.5  KiB",  # a second space between number and unit
    ],
)
def test_parse_allows_no_other_character(text):
    with pytest.raises(ValueError):
        sizes.parse_size(text)


@pytest.mark.parametrize(
    "text",
    [
        "01.5 KiB",  # digits before the "." start with 0
        "00 B",  # more than the single digit 0
        "1.50 KiB",  # two digits after the "."
        "1 KiB",  # no "." and digit with a unit other than B
        "1.5 B",  # B takes digits only
        ".5 KiB",  # no digit before the "."
        "1_000 B",  # "_" is not an ASCII digit
        "1٣ B",  # ARABIC-INDIC DIGIT THREE is not an ASCII digit
    ],
)
def test_parse_rejects_a_number_in_another_form(text):
    with pytest.raises(ValueError):
        sizes.parse_size(text)


def test_parse_rejects_a_unit_spelled_another_way():
    with pytest.raises(ValueError):
        sizes.parse_size("1.5 kib")
