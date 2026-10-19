#!/bin/bash
cat > /app/numfmt.py <<'EOF'
import re

_NUMBER = re.compile(r"([+-]?)([0-9]*)(?:\.([0-9]*))?")


def format_decimal(value: str, places: int) -> str:
    """Round a decimal string such as '1234.5' and format it, for example as '1,234.50'."""
    match = _NUMBER.fullmatch(value)
    if match is None or places < 0:
        raise ValueError(f"cannot format {value!r} to {places} places")
    sign, whole, fraction = match.group(1), match.group(2), match.group(3) or ""
    if not whole and not fraction:
        raise ValueError(f"no digits in {value!r}")

    # Work on the magnitude as an exact integer count of 10**-places units.
    kept, dropped = fraction[:places].ljust(places, "0"), fraction[places:]
    units = int((whole or "0") + kept)
    if dropped and dropped[0] >= "5":  # halfway or more: away from zero
        units += 1

    digits = str(units).rjust(places + 1, "0")
    split = len(digits) - places
    text = f"{int(digits[:split]):,}"
    if places:
        text += "." + digits[split:]
    return ("-" if sign == "-" and units else "") + text
EOF
