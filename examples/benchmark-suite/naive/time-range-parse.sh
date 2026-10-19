#!/bin/bash
cat > /app/timerange.py <<'EOF'
import re

_WORDS = {"noon": 720, "midnight": 0}
_CLOCK = re.compile(r"(\d{1,2})(?::(\d{2}))?(am|pm)?")


def _minutes(token: str) -> int:
    if token in _WORDS:
        return _WORDS[token]
    match = _CLOCK.fullmatch(token)
    if match is None:
        raise ValueError(f"invalid time: {token!r}")
    hour, minute, suffix = int(match[1]), int(match[2] or 0), match[3]
    if minute > 59:
        raise ValueError(f"invalid time: {token!r}")
    if suffix is None:
        if match[2] is None or hour > 23:
            raise ValueError(f"invalid time: {token!r}")
    else:
        if not 1 <= hour <= 12:
            raise ValueError(f"invalid time: {token!r}")
        hour = hour % 12 + (12 if suffix == "pm" else 0)
    return hour * 60 + minute


def parse_range(text: str) -> tuple[int, int]:
    """Parse a time range such as '9am-5:30pm' into (start_minutes, duration_minutes)."""
    parts = re.split(r"\s*[-–]\s*", text.strip().lower())
    if len(parts) != 2:
        raise ValueError(f"invalid range: {text!r}")
    start, end = _minutes(parts[0]), _minutes(parts[1])
    return start, (end - start) % 1440
EOF
