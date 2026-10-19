#!/bin/bash
cat > /app/logwindow.py <<'EOF'
import re
from datetime import datetime, timedelta, timezone

# YYYY-MM-DDTHH:MM:SS, optional fraction of 1 to 6 digits, required UTC offset.
_TIMESTAMP = (
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})"
    r"(?:\.([0-9]{1,6}))?(?:Z|([+-])([0-9]{2}):([0-9]{2}))"
)
_WHOLE = re.compile(_TIMESTAMP)
# A record's first line: the timestamp at the very first character, exactly one space, then a
# level of one or more characters other than the space.
_RECORD = re.compile(_TIMESTAMP + r" ([^ ]+)")


def _instant(match: re.Match[str] | None) -> datetime | None:
    """The instant of a matched timestamp, or None when it is not a valid timestamp."""
    if match is None:
        return None
    fields = match.groups()
    year, month, day, hour, minute, second = (int(field) for field in fields[:6])
    fraction, sign, off_hours, off_minutes = fields[6:10]
    offset = timedelta(0)
    if sign is not None:
        # datetime would accept +05:60 as +06:00, so the offset's ranges are checked here.
        if int(off_hours) > 23 or int(off_minutes) > 59:
            return None
        offset = timedelta(hours=int(off_hours), minutes=int(off_minutes))
        if sign == "-":
            offset = -offset
    try:
        # datetime rejects a month, day, hour, minute or second that does not exist.
        microsecond = int((fraction or "0").ljust(6, "0"))
        local = datetime(year, month, day, hour, minute, second, microsecond)
        return local.replace(tzinfo=timezone(offset))
    except ValueError:
        return None


def count_levels(lines: list[str], start: str, end: str) -> dict[str, int]:
    """Count, per level, the lines of the log records timestamped in the window [start, end)."""
    first, last = _instant(_WHOLE.fullmatch(start)), _instant(_WHOLE.fullmatch(end))
    if first is None or last is None:
        raise ValueError("start and end must be valid timestamps")
    counts: dict[str, int] = {}
    # Level of the record the current line belongs to, or None when that record is not counted
    # (it is outside the window, or no record has started yet).
    current: str | None = None
    for line in lines:
        match = _RECORD.match(line)
        instant = _instant(match)
        if match is not None and instant is not None:
            current = match.group(11) if first <= instant < last else None
        if current is not None:
            counts[current] = counts.get(current, 0) + 1
    return counts
EOF
