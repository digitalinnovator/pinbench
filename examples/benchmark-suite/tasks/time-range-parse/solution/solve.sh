#!/bin/bash
cat > /app/timerange.py <<'EOF'
import re

_DAY = 24 * 60
_WORDS = {"noon": 12 * 60, "midnight": 0}
_TWENTY_FOUR = re.compile(r"([01]?[0-9]|2[0-3]):([0-5][0-9])")
_TWELVE = re.compile(r"(1[0-2]|[1-9])(?::([0-5][0-9]))?(am|pm)")
_SEPARATOR = re.compile(r" *[-–] *")


def _minutes(token: str) -> int:
    """Minutes after 00:00 for one time of day."""
    if token in _WORDS:
        return _WORDS[token]
    match = _TWENTY_FOUR.fullmatch(token)
    if match is not None:
        return int(match[1]) * 60 + int(match[2])
    match = _TWELVE.fullmatch(token)
    if match is not None:
        hour = int(match[1]) % 12 + (12 if match[3] == "pm" else 0)
        return hour * 60 + int(match[2] or 0)
    raise ValueError(f"invalid time: {token!r}")


def parse_range(text: str) -> tuple[int, int]:
    """Parse a time range such as '9am-5:30pm' into (start_minutes, duration_minutes)."""
    parts = _SEPARATOR.split(text.lower())
    if len(parts) != 2:
        raise ValueError(f"invalid range: {text!r}")
    start, end = _minutes(parts[0]), _minutes(parts[1])
    duration = (end - start) % _DAY or _DAY
    return start, duration
EOF
