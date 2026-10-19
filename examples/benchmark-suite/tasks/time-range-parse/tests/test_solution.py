import sys

import pytest

sys.path.insert(0, "/app")
from timerange import parse_range  # noqa: E402

EN_DASH = "–"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("noon-midnight", (720, 720)),
        ("09:05 - 17:45", (545, 520)),
        (f"8:15AM {EN_DASH} Noon", (495, 225)),
        ("12:45pm-13:00", (765, 15)),
        ("5pm-4:59pm", (1020, 1439)),
        ("12am-6am", (0, 360)),
        ("22:30-12:15am", (1350, 105)),
        ("7:30pm-19:30", (1170, 1440)),
        ("midnight-midnight", (0, 1440)),
    ],
)
def test_valid(text, expected):
    assert parse_range(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "9am",
        "9-5",
        "24:00-1:00",
        "13pm-2pm",
        "0am-1am",
        "9:60-10:00",
        "9:5am-10am",
        "9 am-5pm",
        " 9am-5pm",
        "9am-5pm ",
        "9am\t-\t5pm",
        "9am-5pm\n",
        "09am-5pm",
        "9:00am-05:30pm",
    ],
)
def test_invalid(text):
    with pytest.raises(ValueError):
        parse_range(text)


def test_returns_tuple_of_ints():
    result = parse_range("1:00-2:00")
    assert isinstance(result, tuple)
    assert all(type(value) is int for value in result)
