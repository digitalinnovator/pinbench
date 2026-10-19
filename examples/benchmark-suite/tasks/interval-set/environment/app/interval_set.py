from collections.abc import Iterable


class IntervalSet:
    """A set of integers stored as half-open intervals [lo, hi)."""

    def __init__(self) -> None:
        raise NotImplementedError

    @property
    def intervals(self) -> list[tuple[int, int]]:
        raise NotImplementedError

    def add(self, lo: int, hi: int) -> int:
        raise NotImplementedError

    def remove(self, lo: int, hi: int) -> int:
        raise NotImplementedError

    def add_all(self, pairs: Iterable[tuple[int, int]]) -> None:
        raise NotImplementedError

    def add_text(self, text: str) -> None:
        raise NotImplementedError

    def contains(self, x: int) -> bool:
        raise NotImplementedError
