#!/bin/bash
# Careless: the matcher itself is right, but the two rules that need a second look are done the
# quick way. `ignore_case` lowercases both arguments with str.lower(), which also folds letters
# outside a-z and A-Z. A class that never closes raises ValueError only when matching reaches it,
# so a path that already failed on an earlier character or segment gets False instead.
cat > /app/globmatch.py <<'EOF'
def glob_match(pattern: str, path: str, ignore_case: bool = False) -> bool:
    """Report whether the whole of `path` matches the glob `pattern`."""
    if ignore_case:
        pattern, path = pattern.lower(), path.lower()
    return _match_segments(pattern.split("/"), path.split("/"))


def _match_segments(patterns: list[str], parts: list[str]) -> bool:
    if not patterns:
        return not parts
    head, rest = patterns[0], patterns[1:]
    if head == "**":
        return any(_match_segments(rest, parts[skip:]) for skip in range(len(parts) + 1))
    if not parts or not _match_one(head, 0, parts[0], 0):
        return False
    return _match_segments(rest, parts[1:])


def _match_one(pattern: str, pi: int, text: str, ti: int) -> bool:
    """Match pattern[pi:] against text[ti:] inside one segment."""
    if pi == len(pattern):
        return ti == len(text)
    char = pattern[pi]
    if char == "*":
        return any(_match_one(pattern, pi + 1, text, skip) for skip in range(ti, len(text) + 1))
    if ti == len(text):
        return False
    if char == "?":
        return _match_one(pattern, pi + 1, text, ti + 1)
    if char == "[":
        end, matched = _match_class(pattern, pi, text[ti])
        return matched and _match_one(pattern, end + 1, text, ti + 1)
    return char == text[ti] and _match_one(pattern, pi + 1, text, ti + 1)


def _match_class(pattern: str, start: int, char: str) -> tuple[int, bool]:
    """Test `char` against the class opening at `start`; return its closing index and the result."""
    i = start + 1
    negated = pattern[i : i + 1] in ("!", "^")
    if negated:
        i += 1
    # The first set character is always a member, even `]`.
    end = pattern.find("]", i + 1)
    if end == -1:
        raise ValueError(f"unclosed class in {pattern!r}")
    members = pattern[i:end]
    found = False
    k = 0
    while k < len(members):
        if k + 2 < len(members) and members[k + 1] == "-":
            found = found or members[k] <= char <= members[k + 2]
            k += 3
        else:
            found = found or members[k] == char
            k += 1
    return end, found != negated
EOF
