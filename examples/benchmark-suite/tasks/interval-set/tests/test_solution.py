import random
import sys

import pytest

sys.path.insert(0, "/app")
from interval_set import IntervalSet  # noqa: E402

BIG = 10**30


def build(*pairs):
    s = IntervalSet()
    for lo, hi in pairs:
        s.add(lo, hi)
    return s


def canonical(members):
    """The shortest sorted list of half-open intervals that holds exactly `members`."""
    out = []
    for x in sorted(members):
        if out and out[-1][1] == x:
            out[-1] = (out[-1][0], x + 1)
        else:
            out.append((x, x + 1))
    return out


def test_add_keeps_intervals_sorted_and_shortest():
    assert build((10, 12), (1, 3), (5, 7)).intervals == [(1, 3), (5, 7), (10, 12)]
    assert build((1, 5), (3, 8)).intervals == [(1, 8)]
    assert build((1, 3), (5, 7), (9, 11), (2, 10)).intervals == [(1, 11)]
    assert build((-5, -2), (-10, -8), (-3, 1)).intervals == [(-10, -8), (-5, 1)]
    assert build((1, 3), (3, 5)).intervals == [(1, 5)]
    assert build((3, 5), (1, 3)).intervals == [(1, 5)]
    assert build((1, 3), (5, 7), (3, 5)).intervals == [(1, 7)]
    assert build((1, 3), (5, 7), (9, 11), (3, 9)).intervals == [(1, 11)]
    s = build((1, 10))
    s.remove(4, 6)
    s.add(4, 6)
    assert s.intervals == [(1, 10)]


def test_very_large_integers():
    s = build((BIG, BIG + 5), (-BIG, -BIG + 2), (BIG + 3, BIG + 9))
    assert s.intervals == [(-BIG, -BIG + 2), (BIG, BIG + 9)]
    assert s.contains(BIG + 8) and not s.contains(BIG + 9)
    assert s.add(-BIG, BIG) == 2 * BIG - 2
    assert s.remove(BIG + 1, BIG + 20) == 8
    assert s.intervals == [(-BIG, BIG + 1)]


def test_remove():
    cases = [
        ([(1, 10)], (4, 6), [(1, 4), (6, 10)]),  # split
        ([(1, 10)], (1, 4), [(4, 10)]),  # prefix
        ([(1, 10)], (6, 10), [(1, 6)]),  # suffix
        ([(1, 10)], (1, 10), []),  # exact
        ([(1, 5), (8, 12), (15, 20)], (3, 16), [(1, 3), (16, 20)]),  # spans several
        ([(1, 5)], (5, 9), [(1, 5)]),  # after
    ]
    for start, cut, expected in cases:
        s = build(*start)
        s.remove(*cut)
        assert s.intervals == expected, (start, cut)


def test_add_returns_how_many_integers_were_new():
    s = IntervalSet()
    assert s.add(1, 5) == 4
    assert s.add(3, 8) == 3  # 5, 6 and 7 are new
    assert s.add(2, 6) == 0  # all of it was there already
    assert s.add(20, 25) == 5
    assert s.add(10, 12) == 2
    assert s.add(0, 30) == 16  # 30 integers, 7 + 2 + 5 of them already in the set
    assert s.intervals == [(0, 30)]
    s = build((-5, -2))
    assert s.add(-3, 1) == 3  # -2, -1 and 0 are new


def test_remove_returns_how_many_integers_it_took_out():
    s = build((1, 5), (8, 12), (15, 20))
    assert s.remove(3, 16) == 7  # 3, 4; 8 to 11; 15
    assert s.intervals == [(1, 3), (16, 20)]
    assert s.remove(5, 14) == 0  # none of these is in the set
    assert s.remove(0, 2) == 1
    assert s.remove(17, 19) == 2
    assert s.intervals == [(2, 3), (16, 17), (19, 20)]
    assert s.remove(-10, 40) == 3
    assert s.intervals == []


def test_contains_is_half_open():
    s = IntervalSet()
    assert s.intervals == []
    assert not s.contains(0)
    s = build((2, 5), (-4, -1))
    assert [x for x in range(-6, 8) if s.contains(x)] == [-4, -3, -2, 2, 3, 4]
    s = build((1, 10))
    s.remove(4, 6)
    assert [x for x in range(0, 12) if s.contains(x)] == [1, 2, 3, 6, 7, 8, 9]


def test_empty_interval_changes_nothing():
    s = IntervalSet()
    assert s.add(3, 3) == 0
    assert s.remove(0, 0) == 0
    assert s.intervals == []
    assert not s.contains(3)
    s = build((1, 3), (8, 10))
    for point in (5, 3, 0, 9, 8, 1, -7, 20):
        assert s.add(point, point) == 0
        assert s.remove(point, point) == 0
        assert s.intervals == [(1, 3), (8, 10)]
    assert not s.contains(5)
    assert s.contains(9)


def test_lo_greater_than_hi_raises_and_changes_nothing():
    for method in ("add", "remove"):
        s = IntervalSet()
        with pytest.raises(ValueError):
            getattr(s, method)(5, 1)
        assert s.intervals == []
        s = build((1, 5), (8, 12))
        for lo, hi in [(4, 2), (10, 3), (20, 15), (0, -1), (-2, -6)]:
            with pytest.raises(ValueError):
                getattr(s, method)(lo, hi)
            assert s.intervals == [(1, 5), (8, 12)]


def test_add_all_adds_every_pair_of_a_list():
    s = build((20, 25))
    s.add_all([(8, 12), (1, 3), (2, 5)])
    assert s.intervals == [(1, 5), (8, 12), (20, 25)]
    s.add_all([])
    assert s.intervals == [(1, 5), (8, 12), (20, 25)]


def test_add_all_adds_every_pair_of_an_iterable_that_is_not_a_list():
    makers = {
        "generator": lambda pairs: (pair for pair in pairs),
        "iterator": iter,
        "tuple": tuple,
        "zip": lambda pairs: zip([lo for lo, _ in pairs], [hi for _, hi in pairs]),
    }
    for kind, make in makers.items():
        s = build((20, 25))
        s.add_all(make([(8, 12), (1, 3), (2, 5)]))
        assert s.intervals == [(1, 5), (8, 12), (20, 25)], kind
        assert s.contains(4) and not s.contains(5), kind
        s.add_all(make([]))
        assert s.intervals == [(1, 5), (8, 12), (20, 25)], kind


def test_add_all_with_a_reversed_pair_raises_and_adds_nothing():
    # The reversed pair is last, in the middle, first, and the only pair.
    for pairs in (
        [(1, 3), (5, 8), (12, 9)],
        [(1, 3), (9, 4), (10, 12)],
        [(9, 4), (1, 3)],
        [(7, 6)],
    ):
        s = IntervalSet()
        with pytest.raises(ValueError):
            s.add_all(pairs)
        assert s.intervals == [], pairs
        s = build((2, 6), (20, 25))
        with pytest.raises(ValueError):
            s.add_all(pairs)
        assert s.intervals == [(2, 6), (20, 25)], pairs
        with pytest.raises(ValueError):
            s.add_all(pair for pair in pairs)
        assert s.intervals == [(2, 6), (20, 25)], pairs
        assert not s.contains(1) and not s.contains(10), pairs


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("30:40", [(2, 6), (20, 25), (30, 40)]),
        ("-10:-8,-5:1,0:2", [(-10, -8), (-5, 6), (20, 25)]),
        ("8:12, 1:3,   30:40,40:41", [(1, 6), (8, 12), (20, 25), (30, 41)]),
        ("9:9,0:0, -4:-4", [(2, 6), (20, 25)]),
        ("007:010,-0:3, -05:-004", [(-5, -4), (0, 6), (7, 10), (20, 25)]),
        (
            f"{BIG}:{BIG + 5},-{BIG}:-{BIG - 1}",
            [(-BIG, -BIG + 1), (2, 6), (20, 25), (BIG, BIG + 5)],
        ),
    ],
    ids=["one-item", "negative", "spaces-after-commas", "empty-items", "zeros", "large"],
)
def test_add_text_adds_every_item(text, expected):
    s = build((2, 6), (20, 25))
    s.add_text(text)
    assert s.intervals == expected


def test_add_text_with_the_empty_string_adds_nothing():
    s = IntervalSet()
    s.add_text("")
    assert s.intervals == []
    s = build((2, 6), (20, 25))
    s.add_text("")
    assert s.intervals == [(2, 6), (20, 25)]


def raises_value_error(s, text):
    try:
        s.add_text(text)
    except ValueError:
        return True
    return False


# Every text here breaks one stated rule of the form, or has an item with lo > hi.
REJECTED = {
    # Spaces may follow a comma and nothing else.
    "space-not-after-a-comma": [" 30:40", "30:40 ", "30 :40", "30: 40", "30:40 ,50:60", " "],
    # Only the space character may follow a comma; the text has no other characters.
    "whitespace-that-is-not-a-space": ["30:40,\t50:60", "30:40,\n50:60", "30:40\n", "\t30:40"],
    # A number is an optional "-" followed by one or more of the digits 0 to 9.
    "number-form": [
        "+30:40", "30:+40", "3_0:40", "--30:40", "30.0:40", "0x1e:40", "1e2:300", "a:b", "-:40",
        "30:-", "30:4-0",
    ],
    # An item is lo:hi.
    "item-form": ["30", "30:", ":40", "30:40:50", "30-40", "30;40", ":", "(30, 40)"],
    # The items are joined by commas: a comma stands between two items.
    "comma-form": ["30:40,", ",30:40", "30:40,,50:60", "30:40, ", ",", "30:40;50:60"],
    # An item with lo > hi.
    "reversed-item": ["40:30", "30:40,60:50", "60:50, 30:40", "-3:-4"],
}


@pytest.mark.parametrize("kind", list(REJECTED))
def test_add_text_raises_value_error(kind):
    for text in REJECTED[kind]:
        s = IntervalSet()
        assert raises_value_error(s, text), f"no ValueError for {text!r}"
        assert s.intervals == [], repr(text)


@pytest.mark.parametrize(
    "text",
    ["30:40,50:60,x", "30:40,50:60,70:65", "8:9, 30:40,50:+60"],
    ids=["bad-item-last", "reversed-item-last", "bad-number-last"],
)
def test_add_text_that_raises_leaves_the_set_unchanged(text):
    s = build((2, 6), (20, 25))
    with pytest.raises(ValueError):
        s.add_text(text)
    assert s.intervals == [(2, 6), (20, 25)]
    assert not s.contains(8) and not s.contains(30) and not s.contains(55)


def test_intervals_returns_a_new_list_of_tuples():
    s = build((1, 5))
    got = s.intervals
    assert isinstance(got, list)
    assert all(isinstance(pair, tuple) for pair in got)
    got.append((7, 9))
    got[0] = (0, 2)
    assert s.intervals == [(1, 5)]
    assert [x for x in range(-1, 11) if s.contains(x)] == [1, 2, 3, 4]


def test_random_operations_match_a_plain_set():
    rng = random.Random(20260930)
    s = IntervalSet()
    model = set()
    for _ in range(400):
        lo = rng.randint(-10, 10)
        hi = min(10, lo + rng.randint(0, 5))
        span = set(range(lo, hi))
        if rng.random() < 0.5:
            assert s.add(lo, hi) == len(span - model)
            model |= span
        else:
            assert s.remove(lo, hi) == len(span & model)
            model -= span
        assert s.intervals == canonical(model)
        assert all(bool(s.contains(x)) == (x in model) for x in range(-12, 13))
