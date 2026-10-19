#!/bin/bash
cat > /app/splitter.py <<'EOF'
_PARTNER = {")": "(", "]": "[", "}": "{"}
_OPENERS = frozenset(_PARTNER.values())
_QUOTES = "'\""
_TRIMMED = " \t"
_WORD = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

# One character of an item, and whether it is quoting syntax of a top-level string: an
# enclosing quote character or the backslash of an escape.
_Piece = tuple[str, bool]


def _item(pieces: list[_Piece], unquote: bool) -> str:
    """Trim the item, then drop the quoting syntax of its top-level strings if asked.

    A space or tab at either end is always outside a quoted string, because a string starts
    and ends with a quote character, so trimming by character is trimming the exact text.
    """
    first, last = 0, len(pieces)
    while first < last and pieces[first][0] in _TRIMMED:
        first += 1
    while last > first and pieces[last - 1][0] in _TRIMMED:
        last -= 1
    return "".join(char for char, syntax in pieces[first:last] if not (unquote and syntax))


def split_toplevel(text: str, unquote: bool = False) -> list[str]:
    """Split text at the commas that are outside brackets and quoted strings."""
    if not text.strip(_TRIMMED):
        return []
    items: list[str] = []
    pieces: list[_Piece] = []
    open_brackets: list[str] = []
    quote = ""
    toplevel = False  # the current string started while no bracket was open
    escaped = False
    previous = ""
    for char in text:
        syntax = False
        separator = False
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
                syntax = True
            elif char == quote:
                quote = ""
                syntax = True
        elif char in _QUOTES:
            if previous not in _WORD:
                quote = char
                toplevel = not open_brackets
                syntax = True
        elif char in _OPENERS:
            open_brackets.append(char)
        elif char in _PARTNER:
            if not open_brackets or open_brackets.pop() != _PARTNER[char]:
                raise ValueError(f"unmatched {char!r} in {text!r}")
        elif char == "," and not open_brackets:
            separator = True
        previous = char
        if separator:
            items.append(_item(pieces, unquote))
            pieces = []
        else:
            pieces.append((char, syntax and toplevel))
    if quote:
        raise ValueError(f"unclosed quoted string in {text!r}")
    if open_brackets:
        raise ValueError(f"unclosed {open_brackets[-1]!r} in {text!r}")
    items.append(_item(pieces, unquote))
    return items
EOF
