#!/bin/bash
cat > /app/headline.py <<'EOF'
import re

SMALL_WORDS = frozenset(
    {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to"}
)

_RUN = re.compile(r"[^ ]+")
_CLOSERS = ":?!"


def _lead(part: str) -> int:
    """Return the index of the first letter or digit in part, or -1 when it has none."""
    for index, ch in enumerate(part):
        if ch.isalnum():
            return index
    return -1


def _keeps_case(part: str) -> bool:
    lead = _lead(part)
    return lead >= 0 and any(ch.isupper() for ch in part[lead + 1 :])


def _capitalise(part: str) -> str:
    lead = _lead(part)
    if lead < 0 or not part[lead].isalpha():
        return part
    return part[:lead] + part[lead].upper() + part[lead + 1 :]


def _core(word: str) -> str:
    """Return word in lowercase without its leading and trailing non-alphanumerics."""
    start, end = 0, len(word)
    while start < end and not word[start].isalnum():
        start += 1
    while end > start and not word[end - 1].isalnum():
        end -= 1
    return word[start:end].lower()


def _closes_clause(run: str) -> bool:
    """True when only non-alphanumerics follow the last ':', '?' or '!' of run."""
    for ch in reversed(run):
        if ch in _CLOSERS:
            return True
        if ch.isalnum():
            return False
    return False


def _style(word: str, never_small: bool) -> str:
    small = "-" not in word and not never_small and _core(word) in SMALL_WORDS
    parts = []
    for part in word.split("-"):
        if _keeps_case(part):
            parts.append(part)
        elif small:
            parts.append(part.lower())
        else:
            parts.append(_capitalise(part))
    return "-".join(parts)


def _style_line(line: str) -> str:
    runs = list(_RUN.finditer(line))
    words = [index for index, run in enumerate(runs) if _lead(run.group()) >= 0]
    last_word = words[-1] if words else -1
    pieces = []
    position = 0
    clause_start = True
    for index, run in enumerate(runs):
        pieces.append(line[position : run.start()])
        position = run.end()
        text = run.group()
        if index in words:
            pieces.append(_style(text, clause_start or index == last_word))
            clause_start = False
        else:
            pieces.append(text)
        if _closes_clause(text):
            clause_start = True
    pieces.append(line[position:])
    return "".join(pieces)


def headline_case(text: str) -> str:
    """Return text with headline capitalisation, one headline per line."""
    return "\n".join(_style_line(line) for line in text.split("\n"))
EOF
