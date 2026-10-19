#!/bin/bash
cat > /app/ranges.py <<'PYEOF'
"""Compress integers into range text such as '1-3,5,7-9', and expand it back."""

import re
from collections.abc import Iterable

_INT = r"-?\d+"
_ITEM = re.compile(rf"^({_INT})(?:-({_INT}))?$")


def compress(numbers: Iterable[int]) -> str:
    """Return the range text for the given integers."""
    values = sorted(set(numbers))
    items: list[str] = []
    start = 0
    while start < len(values):
        end = start
        while end + 1 < len(values) and values[end + 1] == values[end] + 1:
            end += 1
        if end - start >= 2:
            items.append(f"{values[start]}-{values[end]}")
        else:
            items.extend(str(value) for value in values[start : end + 1])
        start = end + 1
    return ",".join(items)


def expand(text: str) -> list[int]:
    """Return the integers that the range text stands for."""
    if text == "":
        return []
    result: list[int] = []
    for item in re.split(r", *", text):
        match = _ITEM.match(item)
        if match is None:
            raise ValueError(f"malformed item: {item!r}")
        first = int(match[1])
        if match[2] is None:
            result.append(first)
            continue
        last = int(match[2])
        if first >= last:
            raise ValueError(f"range must go upwards: {item!r}")
        result.extend(range(first, last + 1))
    return result
PYEOF
