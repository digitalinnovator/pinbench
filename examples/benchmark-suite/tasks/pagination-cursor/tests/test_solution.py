import sys

import pytest

sys.path.insert(0, "/app")
from pager import fetch_page, remaining  # noqa: E402
from store import Store  # noqa: E402

# (id, created_at) pairs, in the order they are added to the store.
DISTINCT = [("p", 30), ("c", 10), ("z", 50), ("h", 20), ("m", 40)]
DISTINCT_ASC = ["c", "h", "p", "m", "z"]
TIES = [("a", 100), ("b", 200), ("c", 200), ("d", 200), ("e", 300), ("f", 300), ("g", 400)]
SHUFFLED = [("d", 200), ("g", 300), ("b", 200), ("a", 100), ("e", 200), ("c", 300), ("f", 100)]
SHUFFLED_ASC = ["a", "f", "b", "d", "e", "c", "g"]
SIGNED = [("k2", -50), ("k1", -50), ("k0", 0), ("k9", 10), ("k4", -7)]
# Ids are strings of any characters, and they sort as Python compares strings.
ODD = [("b:2", 0), ("a", 0), ("a:", 0), (":a", -5), ("a:1:x", 0), ("x y", -5)]
ODD += [("10", 7), ("9", 7), ("-1", 7)]
ODD_ASC = [":a", "x y", "a", "a:", "a:1:x", "b:2", "-1", "10", "9"]


def make_store(pairs):
    store = Store()
    for id, created_at in pairs:
        store.add(id, created_at)
    return store


def ids(rows):
    return [row["id"] for row in rows]


def walk(store, limit, order="asc"):
    """Follow next_cursor from the first page and return the ids of every row seen, in order."""
    seen, cursor = [], None
    for _ in range(50):
        rows, cursor = fetch_page(store, limit, cursor, order)
        assert len(rows) <= limit
        seen.extend(ids(rows))
        if cursor is None:
            return seen
    raise AssertionError("next_cursor never became None")


@pytest.mark.parametrize(
    "pairs, limit, order, asc_ids",
    [
        (SHUFFLED, 2, "asc", SHUFFLED_ASC),
        (SHUFFLED, 3, "desc", SHUFFLED_ASC),
        (ODD, 1, "asc", ODD_ASC),
        (ODD, 2, "desc", ODD_ASC),
    ],
)
def test_walk_yields_every_row_once_in_order(pairs, limit, order, asc_ids):
    expected = asc_ids if order == "asc" else asc_ids[::-1]
    assert walk(make_store(pairs), limit, order) == expected


def test_next_cursor_is_none_when_no_rows_remain():
    rows, cursor = fetch_page(make_store(DISTINCT), 10)
    assert (ids(rows), cursor) == (DISTINCT_ASC, None)
    rows, cursor = fetch_page(make_store(DISTINCT), 5, None, "desc")
    assert (ids(rows), cursor) == (DISTINCT_ASC[::-1], None)

    store = make_store(DISTINCT[:4])
    first, cursor = fetch_page(store, 2)
    assert ids(first) == ["c", "h"]
    assert cursor is not None
    second, cursor = fetch_page(store, 2, cursor)
    assert (ids(second), cursor) == (["p", "z"], None)

    store = make_store(DISTINCT)
    first, cursor = fetch_page(store, 3)
    assert ids(first) == ["c", "h", "p"]
    store.delete("m")
    store.delete("z")
    rows, cursor = fetch_page(store, 3, cursor)
    assert (ids(rows), cursor) == ([], None)


def test_empty_store():
    for order in ("asc", "desc"):
        rows, cursor = fetch_page(Store(), 3, None, order)
        assert (ids(rows), cursor) == ([], None)
        assert remaining(Store(), None, order) == 0


def test_next_cursor_is_the_cursor_string_of_the_last_row():
    store = make_store(TIES)
    first, cursor = fetch_page(store, 3)
    assert [(row["id"], row["created_at"]) for row in first] == [("a", 100), ("b", 200), ("c", 200)]
    assert cursor == "asc:200:c"
    second, cursor = fetch_page(store, 3, cursor)
    assert ids(second) == ["d", "e", "f"]
    assert cursor == "asc:300:f"
    rows, cursor = fetch_page(store, 2, None, "desc")
    assert [(row["id"], row["created_at"]) for row in rows] == [("g", 400), ("f", 300)]
    assert cursor == "desc:300:f"


def test_cursor_string_with_negative_and_zero_created_at():
    store = make_store(SIGNED)
    assert fetch_page(store, 1)[1] == "asc:-50:k1"
    assert fetch_page(store, 4)[1] == "asc:0:k0"
    assert fetch_page(store, 1, None, "desc")[1] == "desc:10:k9"
    rows, cursor = fetch_page(store, 2, "asc:-50:k1")
    assert (ids(rows), cursor) == (["k2", "k4"], "asc:-7:k4")
    assert remaining(store, "desc:-7:k4", "desc") == 2


def test_next_cursor_holds_the_id_itself():
    store = make_store(ODD)
    assert fetch_page(store, 1)[1] == "asc:-5::a"
    assert fetch_page(store, 2)[1] == "asc:-5:x y"
    assert fetch_page(store, 5)[1] == "asc:0:a:1:x"
    assert fetch_page(store, 7)[1] == "asc:7:-1"
    assert fetch_page(store, 4, None, "desc")[1] == "desc:0:b:2"


def test_cursor_holds_the_id_itself():
    store = make_store(ODD)
    rows, cursor = fetch_page(store, 2, "asc:0:a:")
    assert (ids(rows), cursor) == (["a:1:x", "b:2"], "asc:0:b:2")
    rows, cursor = fetch_page(store, 3, "desc:0:a:1:x", "desc")
    assert (ids(rows), cursor) == (["a:", "a", "x y"], "desc:-5:x y")
    rows, cursor = fetch_page(store, 2, "asc:-5::a")
    assert (ids(rows), cursor) == (["x y", "a"], "asc:0:a")
    assert remaining(store, "asc:-5:x y") == 7
    assert remaining(store, "asc:0:a:1") == 5  # no row has the id "a:1"
    assert remaining(store, "asc:7:007") == 2  # no row has the id "007"


def test_unknown_order_raises_value_error_in_fetch_page():
    with pytest.raises(ValueError):
        fetch_page(make_store(DISTINCT), 2, None, "newest")


def test_unknown_order_raises_value_error_in_remaining():
    with pytest.raises(ValueError):
        remaining(make_store(DISTINCT), None, "newest")


def test_unknown_order_raises_value_error_with_a_cursor():
    store = make_store(TIES)
    for cursor in ("newest:200:b", "asc:200:b"):
        with pytest.raises(ValueError):
            fetch_page(store, 2, cursor, "newest")
        with pytest.raises(ValueError):
            remaining(store, cursor, "newest")


def test_cursor_keeps_its_place_when_rows_are_deleted():
    store = make_store(TIES)
    _, cursor = fetch_page(store, 3)
    store.delete("c")  # the last row of the first page
    assert ids(fetch_page(store, 3, cursor)[0]) == ["d", "e", "f"]
    store.delete("a")  # an earlier row
    assert ids(fetch_page(store, 3, cursor)[0]) == ["d", "e", "f"]

    store = make_store(DISTINCT)
    first, cursor = fetch_page(store, 2, None, "desc")
    assert ids(first) == ["z", "m"]
    store.delete("m")
    assert ids(fetch_page(store, 2, cursor, "desc")[0]) == ["p", "h"]


def test_added_rows_show_up_only_after_the_cursor():
    store = make_store([("k10", 100), ("k20", 200), ("k30", 200), ("k40", 300)])
    first, cursor = fetch_page(store, 2)
    assert ids(first) == ["k10", "k20"]
    store.add("k12", 150)  # earlier timestamp than the last row of the first page
    store.add("k15", 200)  # same timestamp, lower id: still before it
    store.add("k35", 200)  # same timestamp, higher id: after it
    store.add("k50", 250)
    second, cursor = fetch_page(store, 2, cursor)
    third, _ = fetch_page(store, 2, cursor)
    assert (ids(second), ids(third)) == (["k30", "k35"], ["k50", "k40"])


def test_cursor_for_a_position_that_holds_no_row():
    store = make_store(TIES)
    once, _ = fetch_page(store, 2, "asc:200:bb")
    twice, _ = fetch_page(store, 2, "asc:200:bb")
    assert ids(once) == ids(twice) == ["c", "d"]
    assert ids(fetch_page(store, 2, "asc:150:zz")[0]) == ["b", "c"]
    rows, cursor = fetch_page(store, 2, "desc:250:zz", "desc")
    assert (ids(rows), cursor) == (["d", "c"], "desc:200:c")
    assert remaining(store, "asc:350:a") == 1


@pytest.mark.parametrize("first_order, other_order", [("asc", "desc"), ("desc", "asc")])
def test_cursor_is_rejected_by_the_other_order(first_order, other_order):
    store = make_store(TIES)
    _, cursor = fetch_page(store, 2, None, first_order)
    assert cursor is not None
    with pytest.raises(ValueError):
        fetch_page(store, 2, cursor, other_order)
    with pytest.raises(ValueError):
        remaining(store, cursor, other_order)


@pytest.mark.parametrize(
    "cursor",
    [
        "",
        "asc:200",
        "asc:two:b",
        "asc:+200:b",
        "asc:0200:b",
        "asc: 200:b",
        "asc:-0:b",
        "newest:200:b",
    ],
)
def test_string_that_is_not_a_cursor_for_the_order_raises_value_error(cursor):
    store = make_store(TIES)
    with pytest.raises(ValueError):
        fetch_page(store, 2, cursor)
    with pytest.raises(ValueError):
        remaining(store, cursor)


@pytest.mark.parametrize("cursor", [200, ("asc", 200, "b")])
def test_cursor_that_is_not_a_string_raises_value_error(cursor):
    store = make_store(TIES)
    with pytest.raises(ValueError):
        fetch_page(store, 2, cursor)
    with pytest.raises(ValueError):
        remaining(store, cursor)


def test_remaining_counts_the_rows_after_the_cursor():
    store = make_store(TIES)
    assert remaining(store) == 7
    assert remaining(store, None, "desc") == 7
    _, cursor = fetch_page(store, 3)
    assert remaining(store, cursor) == 4
    _, cursor = fetch_page(store, 2, None, "desc")
    assert remaining(store, cursor, "desc") == 5
    assert remaining(store, "asc:400:g") == 0


def test_remaining_follows_added_and_deleted_rows():
    store = make_store(TIES)
    _, cursor = fetch_page(store, 3)
    for id in ("c", "e", "f"):
        store.delete(id)
    store.add("cc", 200)  # same timestamp as the cursor, higher id: after it
    store.add("bb", 200)  # same timestamp, lower id: before it
    assert remaining(store, cursor) == 3
