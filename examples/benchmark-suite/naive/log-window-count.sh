#!/bin/bash
cat > /app/logwindow.py <<'EOF'
import re
from datetime import datetime

_TIMESTAMP = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})"
# A record's first line: a timestamp, one space, then the level.
_RECORD = re.compile(rf"({_TIMESTAMP}) ([^ ]+)")


def _parse(text: str) -> datetime | None:
    """Parse a timestamp; None when it is not a valid one."""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def count_levels(lines: list[str], start: str, end: str) -> dict[str, int]:
    """Count, per level, the lines of the log records timestamped in the window [start, end)."""
    first, last = _parse(start), _parse(end)
    if first is None or last is None:
        raise ValueError("start and end must be valid timestamps")
    counts: dict[str, int] = {}
    level = None
    for line in lines:
        match = _RECORD.match(line)
        timestamp = _parse(match.group(1)) if match else None
        if timestamp is not None:
            level = match.group(2) if first <= timestamp < last else None
        if level is not None:
            counts[level] = counts.get(level, 0) + 1
    return counts
EOF
