import sys

import pytest

sys.path.insert(0, "/app")
from events import apply, apply_all  # noqa: E402
from orders import InvalidTransition, Order  # noqa: E402


def _event(kind, amount=None, id=None):
    event = {"type": kind}
    if amount is not None:
        event["amount"] = amount
    if id is not None:
        event["id"] = id
    return event


def pay(amount, id=None):
    return _event("pay", amount, id)


def refund(amount, id=None):
    return _event("refund", amount, id)


def ship(id=None):
    return _event("ship", id=id)


def cancel(id=None):
    return _event("cancel", id=id)


def build(*events, total=500):
    order = Order(total=total)
    for event in events:
        apply(order, dict(event))
    return order


def core(order):
    return (order.status, order.paid, order.refunded, list(order.history))


def state(order):
    return (*core(order), set(order.seen))


@pytest.mark.parametrize(
    ("events", "expected"),
    [
        ([pay(200), cancel(), refund(200)], ("cancelled", 200, 200, ["pay", "cancel", "refund"])),
        (
            [pay(200), pay(300), refund(100), ship(), refund(400)],
            ("shipped", 500, 500, ["pay", "pay", "refund", "ship", "refund"]),
        ),
    ],
)
def test_accepted(events, expected):
    assert core(build(*events)) == expected


# Each rejected event also carries a well-formed id, which must not reach `seen`.
@pytest.mark.parametrize(
    ("before", "rejected"),
    [
        # status guards
        ([pay(500)], pay(100)),
        ([pay(200)], ship()),
        ([pay(500), ship()], cancel()),
        ([pay(200)], refund(100)),
        # amount guards
        ([pay(200)], pay(400)),
        ([pay(500), refund(300)], refund(300)),
        # amounts that are missing or are not an int above zero
        ([], pay(0)),
        ([], pay(True)),
        ([], pay(500.0)),
        ([], {"type": "pay"}),
        ([pay(500)], {"type": "refund"}),
        # another type, and no type
        ([pay(500)], {"type": "return"}),
        ([pay(500)], {}),
    ],
)
def test_rejected_event_changes_nothing(before, rejected):
    order = build(*before)
    snapshot = state(order)
    with pytest.raises(InvalidTransition):
        apply(order, {**rejected, "id": "x1"})
    assert state(order) == snapshot


def test_duplicate_id_is_ignored():
    order = Order(total=500)
    assert apply(order, pay(200, "p1")) is None
    assert state(order) == ("new", 200, 0, ["pay"], {"p1"})
    assert apply(order, pay(200, "p1")) is None
    assert state(order) == ("new", 200, 0, ["pay"], {"p1"})
    apply(order, pay(200, "p2"))
    assert state(order) == ("new", 400, 0, ["pay", "pay"], {"p1", "p2"})


# No other rule applies to an event whose id is in `seen`: not the status guards, not the amount
# rules, not the type rules.
def test_event_with_a_seen_id_is_ignored_whatever_else_it_holds():
    order = build(pay(500, "p1"), ship("s1"))
    expected = ("shipped", 500, 0, ["pay", "ship"], {"p1", "s1"})
    ignored = [
        pay(500, "p1"),
        ship("s1"),
        pay(True, "s1"),
        {"type": "refund", "id": "p1"},
        {"type": "return", "id": "s1"},
        {"id": "p1"},
    ]
    for event in ignored:
        assert apply(order, event) is None
        assert state(order) == expected


# The "id" key is present and its value is not one or more of the allowed characters. The event
# is a ship on a paid order, so nothing but the id can be the reason to reject it.
@pytest.mark.parametrize("bad_id", [None, "", ["s1"], "s1\n", "café", "s١"])
def test_event_with_an_invalid_id_is_rejected(bad_id):
    order = build(pay(500))
    snapshot = state(order)
    with pytest.raises(InvalidTransition):
        apply(order, {"type": "ship", "id": bad_id})
    assert state(order) == snapshot


def test_id_of_letters_digits_hyphen_and_underscore_is_accepted_and_kept_as_written():
    order = build(pay(500))
    apply(order, ship("Ab-9_z"))
    apply(order, refund(100, "_"))
    assert state(order) == ("shipped", 500, 100, ["pay", "ship", "refund"], {"Ab-9_z", "_"})


def test_ids_that_differ_only_in_case_are_the_same_id():
    order = Order(total=500)
    apply(order, pay(200, "Ab-1"))
    apply(order, pay(200, "aB-1"))
    apply(order, pay(300, "AB-1"))
    assert state(order) == ("new", 200, 0, ["pay"], {"Ab-1"})
    apply(order, pay(300, "ab-2"))
    assert state(order) == ("paid", 500, 0, ["pay", "pay"], {"Ab-1", "ab-2"})


def test_apply_changes_history_and_seen_in_place():
    order = Order(total=500)
    history, seen = order.history, order.seen
    apply(order, pay(500, "p1"))
    apply(order, cancel("c1"))
    assert order.history is history
    assert order.seen is seen
    assert history == ["pay", "cancel"]
    assert seen == {"p1", "c1"}
    assert order.status == "cancelled"


def test_apply_all_accepts_a_valid_batch_in_place():
    order = Order(total=500)
    history, seen = order.history, order.seen
    batch = [pay(200, "p1"), pay(200, "p1"), pay(300, "p2"), ship("s1"), refund(100, "r1")]
    assert apply_all(order, batch) is None
    expected = ("shipped", 500, 100, ["pay", "pay", "ship", "refund"], {"p1", "p2", "s1", "r1"})
    assert state(order) == expected
    assert order.history is history
    assert order.seen is seen


def test_rejected_apply_all_keeps_the_same_history_and_seen_objects():
    order = build(pay(200, "p1"))
    history, seen = order.history, order.seen
    with pytest.raises(InvalidTransition):
        apply_all(order, [pay(300, "p2"), cancel("c1"), ship("s1")])
    assert order.history is history
    assert order.seen is seen
    assert history == ["pay"]
    assert seen == {"p1"}


# The batch starts with an event whose id the order has already seen, then changes every field,
# then fails on its last event. The ids it added are free again afterwards.
def test_rejected_apply_all_leaves_the_order_as_it_was():
    order = build(pay(200, "p1"))
    batch = [pay(200, "p1"), pay(300, "p2"), refund(100, "r1"), ship("s1"), cancel("c1")]
    with pytest.raises(InvalidTransition):
        apply_all(order, batch)
    assert state(order) == ("new", 200, 0, ["pay"], {"p1"})
    apply(order, pay(300, "p2"))
    assert state(order) == ("paid", 500, 0, ["pay", "pay"], {"p1", "p2"})


def test_apply_all_takes_a_generator():
    order = Order(total=500)
    with pytest.raises(InvalidTransition):
        apply_all(order, (event for event in [pay(500, "p1"), ship("s1"), cancel("c1")]))
    assert state(order) == ("new", 0, 0, [], set())
    assert apply_all(order, (event for event in [pay(200, "p1"), pay(300, "p2")])) is None
    assert state(order) == ("paid", 500, 0, ["pay", "pay"], {"p1", "p2"})
