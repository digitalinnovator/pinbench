#!/bin/bash
cat > /app/canonquery.py <<'EOF'
import re
from urllib.parse import quote, unquote_to_bytes

Entry = tuple[bytes, bytes | None]

# A percent sign that is not followed by exactly two ASCII hex digits. The class is spelled out
# because int(text, 16) also accepts a sign, surrounding whitespace and a single digit.
_BAD_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


def _decode(text: str) -> bytes:
    # Only a literal plus is a space, so replace it before %2B is decoded. unquote_to_bytes
    # encodes every other character as UTF-8 and never validates the bytes it produces.
    decoded = unquote_to_bytes(text.replace("+", " "))
    # Trim after decoding, so "+" and "%20" count, and name the byte: a bare strip() would
    # also remove tabs, newlines and the other ASCII whitespace.
    return decoded.strip(b" ")


def canonical_query(query: str) -> str:
    """Return the canonical form of a URL query string such as 'b=2&a=1'."""
    # "&" and "=" are not hex digits, so checking the whole query equals checking each part.
    if _BAD_ESCAPE.search(query):
        raise ValueError("a '%' is not followed by two hex digits")
    if query.startswith("?"):
        query = query[1:]  # exactly one; a second "?" belongs to the first key
    entries: list[Entry] = []
    for segment in query.split("&"):
        if not segment:
            continue
        key, has_value, value = segment.partition("=")
        # None (no value) and b"" (empty value) stay distinct, here and in the output.
        entries.append((_decode(key), _decode(value) if has_value else None))
    # Of duplicates the last one is kept, at its own position in the input.
    last = {entry: index for index, entry in enumerate(entries)}
    kept = [entry for index, entry in enumerate(entries) if last[entry] == index]
    # list.sort is stable, so entries with equal keys keep their input order.
    kept.sort(key=lambda entry: entry[0])
    parts = []
    for key, value in kept:
        part = quote(key, safe="")
        if value is not None:
            part += "=" + quote(value, safe="")
        parts.append(part)
    return "&".join(parts)
EOF
