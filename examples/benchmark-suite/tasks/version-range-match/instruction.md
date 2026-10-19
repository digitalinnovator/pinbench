Implement `satisfies(version: str, spec: str) -> bool` in `/app/semver_range.py`: does the version
match the spec? Raise `ValueError` if `version` is not a version or `spec` is not a spec, as
defined below. `/app/test_semver_range.py` holds a small sample test.

A version is `MAJOR.MINOR.PATCH`, optionally followed by `-` and a pre-release: one or more
dot-separated non-empty identifiers made of ASCII letters, digits and hyphens. A number (`MAJOR`,
`MINOR`, `PATCH`, `N` or `M` below, or an all-digit identifier) is written as `0` or as ASCII
digits not starting with `0`.

Versions are ordered by major, then minor, then patch, compared as numbers. When those are equal:
- A version with a pre-release is lower than one without.
- Two pre-releases are compared identifier by identifier from the left. An all-digit identifier
  is numeric: two numeric ones compare as numbers, a numeric one is lower than a non-numeric
  one, and two non-numeric ones compare as ASCII strings. If every shared position is equal,
  the pre-release with fewer identifiers is lower.

A spec is one or more comparators separated by single spaces, with no other whitespace; the
version must match all of them. Bumping major, minor or patch adds one to it, zeroes the parts
after it and drops the pre-release. A comparator has one of these forms, where `V` is a version
written directly after the operator, and matches the versions that are:
- `V` or `=V`: equal to `V`.
- `>V`, `>=V`, `<V`, `<=V`: higher / not lower / lower / not higher than `V`.
- `~V`: `>=V` and lower than `V` with its minor bumped.
- `^V`: `>=V` and lower than `V` with its leftmost non-zero part bumped (the patch if all are 0).
- `N.x`, `N.M.x`: matched by `>=N.0.0 <(N+1).0.0` and by `>=N.M.0 <N.(M+1).0` respectively.
