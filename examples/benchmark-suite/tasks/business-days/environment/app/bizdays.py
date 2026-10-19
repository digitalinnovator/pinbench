from collections.abc import Iterable
from datetime import date


def add_business_days(
    start: date | str,
    n: int,
    holidays: Iterable[date | str] = (),
    substitute: bool = False,
) -> date:
    """Return the date that lies `n` business days from `start`."""
    raise NotImplementedError
