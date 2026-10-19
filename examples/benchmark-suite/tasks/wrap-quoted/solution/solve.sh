#!/bin/bash
cat > /app/wrapper.py <<'EOF'
import re
from itertools import groupby

QUOTE_MARK = ">"
QUOTE_PREFIX = "> "
# Whitespace is the space and the tab, nothing else: str.split() and str.strip() would also
# break at a non-breaking space, a form feed and every other Unicode space.
_WORD = re.compile(r"[^ \t]+")


def _words(line: str) -> list[str]:
    return _WORD.findall(line)


def _kind(line: str) -> str:
    """Classify an input line as "blank", "quote" or "plain"."""
    if not _words(line):
        return "blank"
    return "quote" if line.startswith(QUOTE_MARK) else "plain"


def _lead(first_word: str, quote: bool) -> str:
    """What an output line starts with, given the word that opens it."""
    if quote:
        return QUOTE_PREFIX
    # A plain line must not come out looking like a quote line.
    return " " if first_word.startswith(QUOTE_MARK) else ""


def _fill(words: list[str], width: int, quote: bool) -> list[str]:
    """Greedy fill. A word is never split, so an overlong word gets a line of its own."""
    lines: list[str] = []
    current: list[str] = []
    lead = ""
    length = 0
    for word in words:
        if current and length + 1 + len(word) > width:
            lines.append(lead + " ".join(current))
            current = []
        if current:
            length += 1 + len(word)
        else:
            # The lead depends on the word that opens the line and counts toward the width.
            lead = _lead(word, quote)
            length = len(lead) + len(word)
        current.append(word)
    if current:
        lines.append(lead + " ".join(current))
    return lines


def wrap_text(text: str, width: int) -> str:
    """Re-wrap the paragraphs of `text` to lines of at most `width` characters."""
    output: list[str] = []
    # A paragraph is a maximal run of lines of one kind, so a quote line that directly
    # follows a plain line starts a new paragraph.
    for kind, group in groupby(text.split("\n"), key=_kind):
        lines = list(group)
        if kind == "blank":
            output.extend("" for _ in lines)
        elif kind == "quote":
            words = [word for line in lines for word in _words(line[len(QUOTE_MARK):])]
            output.extend(_fill(words, width, quote=True))
        else:
            words = [word for line in lines for word in _words(line)]
            output.extend(_fill(words, width, quote=False))
    return "\n".join(output)
EOF
