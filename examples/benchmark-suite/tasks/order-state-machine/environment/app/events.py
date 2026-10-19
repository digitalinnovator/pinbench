"""Order events: pay, ship, cancel and refund."""

from collections.abc import Iterable

from orders import InvalidTransition, Order  # noqa: F401


def apply(order: Order, event: dict) -> None:
    """Apply one event to the order."""
    raise NotImplementedError


def apply_all(order: Order, events: Iterable[dict]) -> None:
    """Apply the events to the order, in order."""
    raise NotImplementedError
