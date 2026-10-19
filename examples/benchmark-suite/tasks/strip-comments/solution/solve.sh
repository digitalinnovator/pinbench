#!/bin/bash
cat > /app/confstrip.py <<'EOF'
def _string_end(source: str, start: int) -> int:
    """Index just past the string that opens at `start`; it never crosses a newline."""
    quote = source[start]
    i = start + 1
    n = len(source)
    while i < n and source[i] != "\n":
        if source[i] == quote:
            return i + 1
        # Only a double-quoted string has escapes, and an escape never swallows a newline.
        if quote == '"' and source[i] == "\\" and i + 1 < n and source[i + 1] != "\n":
            i += 2
        else:
            i += 1
    return i


def strip_comments(source: str) -> str:
    """Remove # line comments and /* */ block comments from config text."""
    out: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in "\"'":
            end = _string_end(source, i)
            out.append(source[i:end])
            i = end
        elif ch == "#":
            newline = source.find("\n", i)
            i = n if newline == -1 else newline
        elif source.startswith("/*", i):
            close = source.find("*/", i + 2)
            end = n if close == -1 else close + 2
            out.append("\n" * source.count("\n", i, end))
            i = end
        else:
            out.append(ch)
            i += 1
    return "".join(out)
EOF
