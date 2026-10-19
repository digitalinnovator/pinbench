"""Order model. All amounts are whole cents."""

from dataclasses import dataclass, field


class InvalidTransition(Exception):
    """Raised when an event is rejected."""


@dataclass
class Order:
    total: int  # price of the order
    status: str = "new"  # "new", "paid", "shipped" or "cancelled"
    paid: int = 0  # received so far
    refunded: int = 0  # given back so far
    history: list[str] = field(default_factory=list)  # types of the accepted events
    seen: set[str] = field(default_factory=set)  # ids of the accepted events
