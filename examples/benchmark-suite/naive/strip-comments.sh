#!/bin/bash
# Plausible careless solution. Three hurried slips:
#  - a closing quote counts as escaped whenever the character before it is a backslash,
#    so a string ending in an escaped backslash never closes;
#  - both quote characters share that one escape check, although a backslash is an ordinary
#    character in a single-quoted string;
#  - an unclosed block comment just stops the scan, dropping the newlines inside it.
cat > /app/confstrip.py <<'EOF'
def strip_comments(source: str) -> str:
    """Remove # line comments and /* */ block comments from config text."""
    out = []
    quote = ""
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if quote:
            out.append(ch)
            if ch == "\n" or (ch == quote and source[i - 1] != "\\"):
                quote = ""
            i += 1
        elif ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
        elif ch == "#":
            end = source.find("\n", i)
            i = n if end == -1 else end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            if end == -1:
                break
            out.append("\n" * source.count("\n", i, end))
            i = end + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)
EOF
