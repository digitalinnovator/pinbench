#!/bin/bash
cat > /app/events.py <<'EOF'
"""Order events: pay, ship, cancel and refund."""

import re
from collections.abc import Iterable

from orders import InvalidTransition, Order

_ID = re.compile(r"[A-Za-z0-9_-]+")


def _amount(event: dict) -> int:
    amount = event.get("amount")
    if type(amount) is not int or amount <= 0:  # bool is a subclass of int: excluded
        raise InvalidTransition(f"invalid amount: {amount!r}")
    return amount


def _require(order: Order, kind: object, *allowed: str) -> None:
    if order.status not in allowed:
        raise InvalidTransition(f"{kind} is not allowed when the order is {order.status}")


def _is_seen(order: Order, event_id: str) -> bool:
    """Ids match whatever the case of their letters; `seen` keeps each id as first written."""
    folded = event_id.lower()
    return any(known.lower() == folded for known in order.seen)


def apply(order: Order, event: dict) -> None:
    """Apply one event to the order. Every guard runs before the first change."""
    has_id = "id" in event  # a key that is present counts, whatever its value (None included)
    event_id = event.get("id")
    if has_id:
        # The type check comes first: an unhashable value must not reach the lookup in `seen`.
        if not isinstance(event_id, str) or _ID.fullmatch(event_id) is None:
            raise InvalidTransition(f"invalid id: {event_id!r}")
        if _is_seen(order, event_id):
            return
    kind = event.get("type")
    if kind == "pay":
        amount = _amount(event)
        _require(order, kind, "new")
        if order.paid + amount > order.total:
            raise InvalidTransition("payment exceeds the order total")
        order.paid += amount
        if order.paid == order.total:
            order.status = "paid"
    elif kind == "ship":
        _require(order, kind, "paid")
        order.status = "shipped"
    elif kind == "cancel":
        _require(order, kind, "new", "paid")
        order.status = "cancelled"
    elif kind == "refund":
        amount = _amount(event)
        _require(order, kind, "paid", "shipped", "cancelled")
        if amount > order.paid - order.refunded:
            raise InvalidTransition("refund exceeds the amount not yet refunded")
        order.refunded += amount
    else:
        raise InvalidTransition(f"unknown event type: {kind!r}")
    order.history.append(kind)
    if has_id:
        order.seen.add(event_id)


def apply_all(order: Order, events: Iterable[dict]) -> None:
    """Apply the events to the order, in order: all of them or none.

    The events are read once, so a generator works. A rejected batch is undone in the order's own
    list and set: their contents go back, the objects stay the same.
    """
    status, paid, refunded = order.status, order.paid, order.refunded
    history, seen = list(order.history), set(order.seen)
    try:
        for event in events:
            apply(order, event)
    except InvalidTransition:
        order.status, order.paid, order.refunded = status, paid, refunded
        order.history[:] = history
        order.seen.clear()
        order.seen.update(seen)
        raise
EOF
