#!/bin/bash
# Plausible careless solution. It cuts the comment off at the first '#' before it looks at the
# value, handles both kinds of quote in one branch (so escapes apply to single quotes too), and
# uses str.strip() and \s, which treat more characters than space and tab as blanks.
cat > /app/envfile.py <<'EOF'
import re

_LINE = re.compile(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)")
_ESCAPE = re.compile(r'\\([nt"\\])')
_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def parse_env(text: str) -> dict[str, str]:
    """Parse the text of a .env file into a dict of keys and values."""
    result: dict[str, str] = {}
    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"line {number}: expected KEY=VALUE")
        key, value = match.groups()
        value = value.split("#", 1)[0].strip()  # drop the inline comment
        if value[:1] in ("'", '"'):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"line {number}: quote is never closed")
            value = _ESCAPE.sub(lambda m: _ESCAPES[m.group(1)], value[1:-1])
        result[key] = value
    return result
EOF
