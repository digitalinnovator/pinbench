import sys

import pytest

sys.path.insert(0, "/app")
from ranges import compress, expand  # noqa: E402


@pytest.mark.parametrize(
    ("numbers", "text"),
    [
        ([1, 2, 3, 4, 6, 8, 9, 10], "1-4,6,8-10"),
        ([], ""),
        ([1, 2, 4, 5, 6, 8, 9], "1,2,4-6,8,9"),
        ([5, 3, 1, 4, 3, 10, 5], "1,3-5,10"),
        ([-3, -2, -1], "-3--1"),
        ({-5, -4, -1, 0, 1, 3}, "-5,-4,-1-1,3"),
    ],
)
def test_compress(numbers, text):
    assert compress(numbers) == text


def test_compress_generator():
    assert compress(n for n in (12, 10, 11, 20)) == "10-12,20"


@pytest.mark.parametrize(
    ("text", "numbers"),
    [
        ("", []),
        ("-3--1", [-3, -2, -1]),
        ("-2-1,-7", [-2, -1, 0, 1, -7]),
        ("5,1-2,2", [5, 1, 2, 2]),
        ("1-3, 8,  9", [1, 2, 3, 8, 9]),
        ("-1-0,0-2,10,-100", [-1, 0, 0, 1, 2, 10, -100]),
    ],
)
def test_expand(text, numbers):
    assert expand(text) == numbers


@pytest.mark.parametrize(
    "text",
    ["3-1", "4-4", "1,,2", "1, ,2", "1-2-3", "1 - 3", " 1,2", "1 ", "+3", "1,\t2"],
)
def test_expand_malformed(text):
    with pytest.raises(ValueError):
        expand(text)


# The first digit is 0 only when it is the only digit, and zero has no "-".
@pytest.mark.parametrize("text", ["01", "5,1-03", "-0", "-01"])
def test_expand_integer_form(text):
    with pytest.raises(ValueError):
        expand(text)


# Digits are ASCII only: U+0663 is ARABIC-INDIC DIGIT THREE, U+FF15 is FULLWIDTH DIGIT FIVE.
@pytest.mark.parametrize("text", ["1\u0663", "2-1\uff15"])
def test_expand_ascii_digits_only(text):
    with pytest.raises(ValueError):
        expand(text)


def test_expand_nothing_after_last_item():
    with pytest.raises(ValueError):
        expand("1-3,5\n")
