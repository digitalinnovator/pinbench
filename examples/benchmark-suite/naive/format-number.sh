#!/bin/bash
# Careless solution: checks the text with an anchored pattern, then leans on Decimal for the
# rounding. It never tries a trailing newline or a value longer than Decimal's default precision.
cat > /app/numfmt.py <<'EOF'
import re
from decimal import ROUND_HALF_UP, Decimal

_VALUE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)$")


def format_decimal(value: str, places: int) -> str:
    """Round a decimal string such as '1234.5' and format it, for example as '1,234.50'."""
    if places < 0 or not _VALUE.match(value):
        raise ValueError(f"cannot format {value!r} to {places} places")
    step = Decimal(1).scaleb(-places)
    rounded = Decimal(value).quantize(step, rounding=ROUND_HALF_UP)
    sign = "-" if rounded < 0 else ""
    whole, _, fraction = f"{abs(rounded):f}".partition(".")
    return sign + f"{int(whole):,}" + ("." + fraction if places else "")
EOF
