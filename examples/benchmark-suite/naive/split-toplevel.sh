#!/bin/bash
cat > /app/splitter.py <<'EOF'
_PAIRS = {")": "(", "]": "[", "}": "{"}
_OPENERS = set(_PAIRS.values())
_QUOTES = "'\""


def split_toplevel(text: str, unquote: bool = False) -> list[str]:
    """Split text at the commas that are outside brackets and quoted strings."""
    if text.strip(" \t") == "":
        return []
    items: list[str] = []
    current: list[str] = []
    stack: list[str] = []
    quote = ""
    strip_quotes = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if quote:
            if ch == "\\" and i + 1 < n:
                if not strip_quotes:
                    current.append(ch)
                current.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
                if not strip_quotes:
                    current.append(ch)
            else:
                current.append(ch)
        elif ch in _QUOTES and not (i > 0 and text[i - 1].isalnum()):
            quote = ch
            strip_quotes = unquote and not stack
            if not strip_quotes:
                current.append(ch)
        elif ch in _OPENERS:
            stack.append(ch)
            current.append(ch)
        elif ch in _PAIRS:
            if not stack or stack.pop() != _PAIRS[ch]:
                raise ValueError(f"unmatched closing bracket {ch!r} at position {i}")
            current.append(ch)
        elif ch == "," and not stack:
            items.append("".join(current).strip(" \t"))
            current = []
        else:
            current.append(ch)
        i += 1
    if quote:
        raise ValueError("unterminated quoted string")
    if stack:
        raise ValueError(f"unclosed bracket {stack[-1]!r}")
    items.append("".join(current).strip(" \t"))
    return items
EOF
