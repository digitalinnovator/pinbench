#!/bin/bash
cat > /app/globmatch.py <<'EOF'
from collections.abc import Callable

# One token per pattern element: None stands for `*`, anything else tests a single character.
Token = Callable[[str], bool] | None
# A compiled pattern segment: None stands for `**`.
Segment = list[Token] | None


def glob_match(pattern: str, path: str, ignore_case: bool = False) -> bool:
    """Report whether the whole of `path` matches the glob `pattern`."""
    # Every segment is compiled before any matching, so a malformed pattern raises for any path.
    segments = [
        None if segment == "**" else _tokens(segment, ignore_case) for segment in pattern.split("/")
    ]
    return _match_segments(segments, path.split("/"))


def _match_segments(segments: list[Segment], parts: list[str]) -> bool:
    if not segments:
        return not parts
    head, rest = segments[0], segments[1:]
    if head is None:
        return any(_match_segments(rest, parts[skip:]) for skip in range(len(parts) + 1))
    if not parts or not _match_one(head, parts[0]):
        return False
    return _match_segments(rest, parts[1:])


def _match_one(tokens: list[Token], text: str) -> bool:
    """Match one path segment, tracking every offset the tokens so far can end at."""
    ends = {0}
    for token in tokens:
        if token is None:
            ends = set(range(min(ends), len(text) + 1)) if ends else ends
        else:
            ends = {end + 1 for end in ends if end < len(text) and token(text[end])}
    return len(text) in ends


def _other_case(char: str) -> str:
    """The other case of one of the 52 letters a-z and A-Z; any other character unchanged."""
    if "a" <= char <= "z":
        return chr(ord(char) - 32)
    if "A" <= char <= "Z":
        return chr(ord(char) + 32)
    return char


def _tokens(segment: str, ignore_case: bool) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    while i < len(segment):
        char = segment[i]
        if char == "*":
            tokens.append(None)
        elif char == "?":
            tokens.append(lambda c: True)
        elif char == "[":
            i, in_set, negated = _parse_class(segment, i)
            tokens.append(_class_test(in_set, negated, ignore_case))
        elif ignore_case:
            tokens.append(lambda c, literal=char: c == literal or _other_case(c) == literal)
        else:
            tokens.append(lambda c, literal=char: c == literal)
        i += 1
    return tokens


def _class_test(
    in_set: Callable[[str], bool], negated: bool, ignore_case: bool
) -> Callable[[str], bool]:
    if ignore_case:
        return lambda c: (in_set(c) or in_set(_other_case(c))) != negated
    return lambda c: in_set(c) != negated


def _parse_class(segment: str, start: int) -> tuple[int, Callable[[str], bool], bool]:
    """Parse the class opening at `start`; return its closing index, its set test and negation."""
    i = start + 1
    negated = segment[i : i + 1] in ("!", "^")
    if negated:
        i += 1
    # The first set character is always a member, even `]`, so the class closes after it.
    end = segment.find("]", i + 1)
    if end == -1:
        raise ValueError(f"class opened at offset {start} of {segment!r} is never closed")
    members = segment[i:end]
    ranges: list[tuple[str, str]] = []
    k = 0
    while k < len(members):
        if k + 2 < len(members) and members[k + 1] == "-":
            # A reversed range is kept as written: no character lies between its bounds.
            ranges.append((members[k], members[k + 2]))
            k += 3
        else:
            ranges.append((members[k], members[k]))
            k += 1
    return end, lambda c: any(low <= c <= high for low, high in ranges), negated
EOF
