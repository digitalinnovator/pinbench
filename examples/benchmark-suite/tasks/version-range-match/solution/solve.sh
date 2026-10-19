#!/bin/bash
cat > /app/semver_range.py <<'EOF'
import operator
import re

_NUMBER = r"(?:0|[1-9][0-9]*)"
_ID = r"[0-9A-Za-z-]+"
_VERSION = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})(?:-({_ID}(?:\.{_ID})*))?"
)
_X_RANGE = re.compile(rf"({_NUMBER})(?:\.({_NUMBER}))?\.x")
_OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "=": operator.eq,
}
_RELEASE = (1,)  # sorts above every pre-release key, which starts with 0


def _release(major: int, minor: int, patch: int) -> tuple:
    return (major, minor, patch, _RELEASE)


def _identifier(part: str) -> tuple:
    """Key for one pre-release identifier: numeric ones sort below the others."""
    if not part.isdigit():
        return (1, 0, part)
    if re.fullmatch(_NUMBER, part) is None:
        raise ValueError(f"numeric identifier with a leading zero: {part!r}")
    return (0, int(part), "")


def _parse(text: str) -> tuple:
    """Turn a version into a key whose tuple ordering is the version ordering."""
    match = _VERSION.fullmatch(text)
    if match is None:
        raise ValueError(f"invalid version: {text!r}")
    major, minor, patch = (int(group) for group in match.groups()[:3])
    if match.group(4) is None:
        return _release(major, minor, patch)
    identifiers = tuple(_identifier(part) for part in match.group(4).split("."))
    return (major, minor, patch, (0, identifiers))


def _expand(comparator: str) -> list[tuple]:
    """Turn one comparator into (operator function, version key) checks."""
    x_range = _X_RANGE.fullmatch(comparator)
    if x_range is not None:
        major = int(x_range.group(1))
        if x_range.group(2) is None:
            low, high = _release(major, 0, 0), _release(major + 1, 0, 0)
        else:
            minor = int(x_range.group(2))
            low, high = _release(major, minor, 0), _release(major, minor + 1, 0)
        return [(operator.ge, low), (operator.lt, high)]
    if comparator[:1] in ("^", "~"):
        low = _parse(comparator[1:])
        major, minor, patch = low[:3]
        if comparator[0] == "~" or (major == 0 and minor != 0):
            high = _release(major, minor + 1, 0)
        elif major != 0:
            high = _release(major + 1, 0, 0)
        else:
            high = _release(0, 0, patch + 1)
        return [(operator.ge, low), (operator.lt, high)]
    for symbol, compare in _OPERATORS.items():
        if comparator.startswith(symbol):
            return [(compare, _parse(comparator[len(symbol):]))]
    return [(operator.eq, _parse(comparator))]


def satisfies(version: str, spec: str) -> bool:
    """Report whether a semantic version such as '1.4.0' matches a range such as '^1.2.3'."""
    key = _parse(version)
    # Splitting on one space turns a doubled, leading or trailing space into an empty
    # comparator, which fails to parse. Every comparator is parsed before any is evaluated.
    checks = [check for comparator in spec.split(" ") for check in _expand(comparator)]
    return all(compare(key, bound) for compare, bound in checks)
EOF
