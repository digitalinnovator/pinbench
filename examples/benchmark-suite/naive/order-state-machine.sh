#!/bin/bash
# Careless solution. It reads the id with event.get, so an "id" key holding None counts as no id.
# Its pattern ends in "$", which also matches before a trailing newline. It lower-cases the id on
# the way in, so `seen` holds the lower-case spelling instead of the one the event wrote. And
# apply_all rolls back by assigning its saved copies, which replaces the history list and the
# seen set.
cat > /app/events.py <<'EOF'
"""Order events: pay, ship, cancel and refund."""

import re
from collections.abc import Iterable

from orders import InvalidTransition, Order

_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _valid_amount(amount: object) -> bool:
    return isinstance(amount, int) and not isinstance(amount, bool) and amount > 0


def apply(order: Order, event: dict) -> None:
    """Apply one event to the order."""
    event_id = event.get("id")
    if event_id is not None:
        if not isinstance(event_id, str) or not _ID.match(event_id):
            raise InvalidTransition(f"invalid id: {event_id!r}")
        event_id = event_id.lower()  # ids are compared without regard to case
        if event_id in order.seen:
            return
    kind = event.get("type")
    amount = event.get("amount")
    if kind in ("pay", "refund") and not _valid_amount(amount):
        raise InvalidTransition(f"invalid amount: {amount!r}")

    if kind == "pay":
        if order.status != "new":
            raise InvalidTransition("order is not awaiting payment")
        if order.paid + amount > order.total:
            raise InvalidTransition("overpayment")
        order.paid += amount
        if order.paid == order.total:
            order.status = "paid"
    elif kind == "ship":
        if order.status != "paid":
            raise InvalidTransition("order is not paid")
        order.status = "shipped"
    elif kind == "cancel":
        if order.status not in ("new", "paid"):
            raise InvalidTransition("order can no longer be cancelled")
        order.status = "cancelled"
    elif kind == "refund":
        if order.status not in ("paid", "shipped", "cancelled"):
            raise InvalidTransition("nothing to refund")
        if amount > order.paid - order.refunded:
            raise InvalidTransition("refund exceeds what is left of the payment")
        order.refunded += amount
    else:
        raise InvalidTransition(f"unknown event type: {kind!r}")
    order.history.append(kind)
    if event_id is not None:
        order.seen.add(event_id)


def apply_all(order: Order, events: Iterable[dict]) -> None:
    """Apply the events to the order, in order."""
    saved = (order.status, order.paid, order.refunded, list(order.history), set(order.seen))
    try:
        for event in events:
            apply(order, event)
    except InvalidTransition:
        order.status, order.paid, order.refunded, order.history, order.seen = saved
        raise
EOF
