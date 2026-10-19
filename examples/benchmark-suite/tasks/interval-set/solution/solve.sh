#!/bin/bash
cat > /app/interval_set.py <<'EOF'
import re
from collections.abc import Iterable

# An item is lo:hi; a number is an optional "-" and then ASCII digits only.
_ITEM = re.compile(r"(-?[0-9]+):(-?[0-9]+)")


class IntervalSet:
    """A set of integers stored as half-open intervals [lo, hi)."""

    def __init__(self) -> None:
        self._intervals: list[tuple[int, int]] = []

    @property
    def intervals(self) -> list[tuple[int, int]]:
        return list(self._intervals)

    @staticmethod
    def _is_empty(lo: int, hi: int) -> bool:
        if lo > hi:
            raise ValueError(f"lo ({lo}) is greater than hi ({hi})")
        return lo == hi

    def add(self, lo: int, hi: int) -> int:
        if self._is_empty(lo, hi):
            return 0
        covered = 0
        new_lo, new_hi = lo, hi
        kept: list[tuple[int, int]] = []
        for start, end in self._intervals:
            if end < lo or hi < start:
                kept.append((start, end))
            else:  # overlaps or touches: absorb it
                covered += max(0, min(end, hi) - max(start, lo))
                new_lo, new_hi = min(new_lo, start), max(new_hi, end)
        kept.append((new_lo, new_hi))
        kept.sort()
        self._intervals = kept
        return (hi - lo) - covered

    def remove(self, lo: int, hi: int) -> int:
        if self._is_empty(lo, hi):
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
        pairs = list(pairs)  # a generator can be read only once
        for lo, hi in pairs:  # check every pair before the set changes
            self._is_empty(lo, hi)
        for lo, hi in pairs:
            self.add(lo, hi)

    def add_text(self, text: str) -> None:
        pairs: list[tuple[int, int]] = []
        if text != "":
            for index, item in enumerate(text.split(",")):
                if index > 0:
                    item = item.lstrip(" ")  # spaces, and only spaces, may follow a comma
                match = _ITEM.fullmatch(item)
                if match is None:
                    raise ValueError(f"malformed interval text: {text!r}")
                pairs.append((int(match.group(1)), int(match.group(2))))
        self.add_all(pairs)  # checks lo > hi for every item before the set changes

    def contains(self, x: int) -> bool:
        return any(start <= x < end for start, end in self._intervals)
EOF
