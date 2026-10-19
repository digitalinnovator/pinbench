#!/bin/bash
cat > /app/envfile.py <<'EOF'
import re

_BLANK = " \t"
_LINE = re.compile(r"(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.DOTALL)
_COMMENT = re.compile(r"[ \t]#")
_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def _single_quoted(value: str, number: int) -> tuple[str, str]:
    """Return the literal content and whatever follows the closing quote."""
    end = value.find("'", 1)
    if end == -1:
        raise ValueError(f"line {number}: single quote is never closed")
    return value[1:end], value[end + 1 :]


def _double_quoted(value: str, number: int) -> tuple[str, str]:
    """Return the unescaped content and whatever follows the closing quote."""
    out: list[str] = []
    i = 1
    while i < len(value):
        char = value[i]
        if char == '"':
            return "".join(out), value[i + 1 :]
        if char == "\\" and i + 1 < len(value) and value[i + 1] in _ESCAPES:
            out.append(_ESCAPES[value[i + 1]])
            i += 2
            continue
        out.append(char)
        i += 1
    raise ValueError(f"line {number}: double quote is never closed")


def _check_tail(tail: str, number: int) -> None:
    """After a closing quote only blanks and a comment (blank then '#') may follow."""
    rest = tail.lstrip(_BLANK)
    if rest and not (rest.startswith("#") and rest != tail):
        raise ValueError(f"line {number}: unexpected text after the closing quote")


def _unquoted(after_equals: str) -> str:
    comment = _COMMENT.search(after_equals)
    if comment is not None:
        after_equals = after_equals[: comment.start()]
    return after_equals.strip(_BLANK)


def parse_env(text: str) -> dict[str, str]:
    """Parse the text of a .env file into a dict of keys and values."""
    result: dict[str, str] = {}
    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw.strip(_BLANK)
        if not line or line.startswith("#"):
            continue
        match = _LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"line {number}: expected KEY=VALUE")
        key, after_equals = match.groups()
        value = after_equals.lstrip(_BLANK)
        if value.startswith("'"):
            result[key], tail = _single_quoted(value, number)
            _check_tail(tail, number)
        elif value.startswith('"'):
            result[key], tail = _double_quoted(value, number)
            _check_tail(tail, number)
        else:
            result[key] = _unquoted(after_equals)
    return result
EOF
