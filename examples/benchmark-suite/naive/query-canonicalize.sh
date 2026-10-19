#!/bin/bash
# Careless solution: a hand-written decoder that follows the instruction's outline, but
# - leaves the hex check to int(), which also accepts a single digit,
# - trims with a bare strip(), which removes every ASCII whitespace byte, not only 0x20,
# - strips every leading "?" instead of one.
cat > /app/canonquery.py <<'EOF'
_UNRESERVED = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def _decode(text: str) -> bytes:
    out = bytearray()
    i = 0
    while i < len(text):
        char = text[i]
        if char == "+":
            out.append(0x20)
            i += 1
        elif char == "%":
            # int() raises ValueError when the two characters are not hex digits.
            out.append(int(text[i + 1 : i + 3], 16))
            i += 3
        else:
            out.extend(char.encode("utf-8"))
            i += 1
    return bytes(out).strip()


def _encode(data: bytes) -> str:
    return "".join(chr(b) if b in _UNRESERVED else "%{:02X}".format(b) for b in data)


def canonical_query(query: str) -> str:
    """Return the canonical form of a URL query string such as 'b=2&a=1'."""
    entries = []
    for segment in query.lstrip("?").split("&"):
        if not segment:
            continue
        key, has_value, value = segment.partition("=")
        entries.append((_decode(key), _decode(value) if has_value else None))
    # Walk backwards so that the last of each group of duplicates is the one kept.
    seen = set()
    kept = []
    for entry in reversed(entries):
        if entry not in seen:
            seen.add(entry)
            kept.append(entry)
    kept.reverse()
    # list.sort is stable, so entries with equal keys keep their order.
    kept.sort(key=lambda entry: entry[0])
    parts = []
    for key, value in kept:
        parts.append(_encode(key) if value is None else _encode(key) + "=" + _encode(value))
    return "&".join(parts)
EOF
