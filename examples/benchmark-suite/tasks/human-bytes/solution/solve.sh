#!/bin/bash
cat > /app/sizes.py <<'PY'
import re

_UNITS = ("KiB", "MiB", "GiB", "TiB")
_BYTES = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4}
# [0-9] rather than \d: \d also matches digits outside ASCII.
_TEXT = re.compile(r"(0|[1-9][0-9]*)(?:\.([0-9]))? (B|KiB|MiB|GiB|TiB)")


def format_size(n: int) -> str:
    """Render a byte count such as 1536 as '1.5 KiB'."""
    if n < 0:
        raise ValueError(f"size must not be negative: {n}")
    if n < 1024:
        return f"{n} B"
    size = 1
    for unit in _UNITS:
        size *= 1024
        # Tenths of a unit in integer arithmetic: nearest, exact halves up, any size of n.
        tenths = (20 * n + size) // (2 * size)
        # Rounding can reach 1024.0, which belongs to the next unit (if there is one).
        if tenths < 10240 or unit == _UNITS[-1]:
            return f"{tenths // 10}.{tenths % 10} {unit}"
    raise AssertionError("unreachable")


def parse_size(text: str) -> int:
    """Read a rendered size such as '1.5 KiB' back into a byte count."""
    match = _TEXT.fullmatch(text)
    if match is None:
        raise ValueError(f"not a size: {text!r}")
    whole, tenth, unit = match.groups()
    # Bytes are written without a decimal place, every other unit with exactly one.
    if (unit == "B") != (tenth is None):
        raise ValueError(f"not a size: {text!r}")
    tenths = 10 * int(whole) + int(tenth or "0")
    return tenths * _BYTES[unit] // 10
PY
