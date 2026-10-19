#!/bin/bash
# Plausible careless solution: one hurried pass that gets the hyphen, lead, existing-capitals and
# small-word matching rules right but takes three shortcuts. It splits lines with splitlines(),
# which drops a final line break and turns "\r\n" into "\n". It splits each line on single spaces
# and finds the first and last word by position in that split, so empty strings from extra spaces
# and runs without a letter or digit are counted as words. It treats a clause as closed only when
# the run just before ends with ":", "?" or "!" itself.
cat > /app/headline.py <<'EOF'
SMALL_WORDS = frozenset(
    {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to"}
)


def _lead(part: str) -> int:
    for index, ch in enumerate(part):
        if ch.isalnum():
            return index
    return len(part)


def _keeps_case(part: str) -> bool:
    return any(ch.isupper() for ch in part[_lead(part) + 1 :])


def _capitalise(part: str) -> str:
    lead = _lead(part)
    return part[:lead] + part[lead : lead + 1].upper() + part[lead + 1 :]


def _core(word: str) -> str:
    start, end = 0, len(word)
    while start < end and not word[start].isalnum():
        start += 1
    while end > start and not word[end - 1].isalnum():
        end -= 1
    return word[start:end].lower()


def _style_line(line: str) -> str:
    words = line.split(" ")
    last = len(words) - 1
    result = []
    for index, word in enumerate(words):
        after_clause = index > 0 and words[index - 1].endswith((":", "?", "!"))
        exempt = index in (0, last) or after_clause
        small = "-" not in word and _core(word) in SMALL_WORDS and not exempt
        if small and not _keeps_case(word):
            result.append(word.lower())
        else:
            parts = [p if _keeps_case(p) else _capitalise(p) for p in word.split("-")]
            result.append("-".join(parts))
    return " ".join(result)


def headline_case(text: str) -> str:
    """Return text with headline capitalisation, one headline per line."""
    return "\n".join(_style_line(line) for line in text.splitlines())
EOF
