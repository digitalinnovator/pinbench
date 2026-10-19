#!/bin/bash
cat > /app/semver_range.py <<'EOF'
import operator

_OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "=": operator.eq,
}


def _parse(text):
    core, _, pre = text.partition("-")
    major, minor, patch = (int(part) for part in core.split("."))
    # A release (no pre-release) sorts after any pre-release of the same version.
    return (major, minor, patch, pre == "", pre.split("."))


def _match(version, comparator):
    if comparator.endswith(".x"):
        wanted = tuple(int(part) for part in comparator[:-2].split("."))
        return version[: len(wanted)] == wanted
    if comparator[0] == "^":
        low = _parse(comparator[1:])
        return low <= version < _parse(f"{low[0] + 1}.0.0")
    if comparator[0] == "~":
        low = _parse(comparator[1:])
        return low <= version < _parse(f"{low[0]}.{low[1] + 1}.0")
    for symbol, compare in _OPERATORS.items():
        if comparator.startswith(symbol):
            return compare(version, _parse(comparator[len(symbol):]))
    return version == _parse(comparator)


def satisfies(version: str, spec: str) -> bool:
    """Report whether a semantic version such as '1.4.0' matches a range such as '^1.2.3'."""
    comparators = spec.split()
    if not comparators:
        raise ValueError("empty spec")
    parsed = _parse(version)
    return all(_match(parsed, comparator) for comparator in comparators)
EOF
