#!/bin/bash
# Plausible careless solution, modelled on what quick attempts actually wrote: Decimal with
# the default 28-digit context for the arithmetic, and the first regex that comes to mind.
# It gets the everyday cases right (unit chosen after rounding, halves up, leading zeros, one
# decimal per unit) and breaks three stated rules:
# - "of any size": past 28 significant digits Decimal raises in format_size and rounds the
#   product in parse_size;
# - "no other character ... after them": `$` also matches before a final newline;
# - "every digit is an ASCII digit": `\d` matches digits of other scripts.
cat > /app/sizes.py <<'PY'
import re
from decimal import ROUND_HALF_UP, Decimal

_UNITS = ["B", "KiB", "MiB", "GiB", "TiB"]
_TEXT = re.compile(r"^(0|[1-9]\d*)(\.\d)? (B|KiB|MiB|GiB|TiB)$")


def format_size(n: int) -> str:
    """Render a byte count such as 1536 as '1.5 KiB'."""
    if n < 0:
        raise ValueError(f"size must not be negative: {n}")
    if n < 1024:
        return f"{n} B"
    last = len(_UNITS) - 1
    for index in range(1, len(_UNITS)):
        value = Decimal(n) / Decimal(1024) ** index
        rounded = value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if rounded < 1024 or index == last:
            return f"{rounded} {_UNITS[index]}"
    raise AssertionError("unreachable")


def parse_size(text: str) -> int:
    """Read a rendered size such as '1.5 KiB' back into a byte count."""
    match = _TEXT.match(text)
    if match is None:
        raise ValueError(f"not a size: {text!r}")
    whole, tenth, unit = match.groups()
    if (unit == "B") != (tenth is None):
        raise ValueError(f"not a size: {text!r}")
    return int(Decimal(whole + (tenth or "")) * 1024 ** _UNITS.index(unit))
PY
