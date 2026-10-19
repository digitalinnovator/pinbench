#!/bin/bash
# Plausible careless solution. The interval logic is right, and three stated rules are broken
# by the obvious code:
# - add_all checks the pairs in one loop and adds them in a second one, so an iterable that
#   can be read only once (a generator, an iterator, a zip) is used up by the check and
#   nothing is added.
# - add_text splits on "," and strips each item, so it accepts any whitespace anywhere
#   around an item (tabs, newlines, a space before a comma), and it reads numbers with
#   int(), which also accepts "+5", "1_0" and spaces next to the ":".
# - add_text adds item by item, so a malformed item leaves the earlier items in the set.
cat > /app/interval_set.py <<'EOF'
from collections.abc import Iterable


class IntervalSet:
    """A set of integers stored as half-open intervals [lo, hi)."""

    def __init__(self) -> None:
        self._intervals: list[tuple[int, int]] = []

    @property
    def intervals(self) -> list[tuple[int, int]]:
        return list(self._intervals)

    def add(self, lo: int, hi: int) -> int:
        if lo > hi:
            raise ValueError("lo must not be greater than hi")
        if lo == hi:
            return 0
        covered = 0
        new_lo, new_hi = lo, hi
        kept: list[tuple[int, int]] = []
        for start, end in self._intervals:
            if end < lo or hi < start:
                kept.append((start, end))
            else:  # overlaps or touches the new interval
                covered += max(0, min(end, hi) - max(start, lo))
                new_lo, new_hi = min(new_lo, start), max(new_hi, end)
        kept.append((new_lo, new_hi))
        kept.sort()
        self._intervals = kept
        return (hi - lo) - covered

    def remove(self, lo: int, hi: int) -> int:
        if lo > hi:
            raise ValueError("lo must not be greater than hi")
        if lo == hi:
            return 0
        taken = 0
        kept: list[tuple[int, int]] = []
        for start, end in self._intervals:
            taken += max(0, min(end, hi) - max(start, lo))
            if start < lo:
                kept.append((start, min(end, lo)))
            if hi < end:
                kept.append((max(start, hi), end))
        self._intervals = kept
        return taken

    def add_all(self, pairs: Iterable[tuple[int, int]]) -> None:
        for lo, hi in pairs:
            if lo > hi:
                raise ValueError("lo must not be greater than hi")
        for lo, hi in pairs:
            self.add(lo, hi)

    def add_text(self, text: str) -> None:
        if not text.strip():
            return
        for item in text.split(","):
            lo, hi = item.strip().split(":")
            self.add(int(lo), int(hi))

    def contains(self, x: int) -> bool:
        return any(start <= x < end for start, end in self._intervals)
EOF
