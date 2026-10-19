Implement `glob_match(pattern: str, path: str, ignore_case: bool = False) -> bool` in
`/app/globmatch.py`. It returns `True` when the whole `path` matches the glob `pattern`, otherwise
`False`. A visible test is in `/app/test_globmatch.py`.

Split the pattern and the path into segments at `/`. The pattern's segments must match the
path's segments in order, with nothing left over on either side:

- A pattern segment that is exactly `**` matches zero or more consecutive path segments.
- Every other pattern segment matches exactly one whole path segment, by the rules below.

Rules inside such a segment:

- `?` matches any one character.
- `*` matches any run of characters, including an empty run. `**` is special only as a whole
  segment; elsewhere it is two `*`.
- `[abc]` matches one character from the set. A set may include inclusive ranges such as `a-z`.
- A range whose end comes before its start contains no characters.
- `[!abc]` and `[^abc]` both match one character that is not in the set.
- A `]` that comes first in the set, after any `!` or `^`, is a member and does not close the class.
- A `[` outside a set always starts a class. A class with no closing `]` in its own segment makes
  the pattern malformed: raise `ValueError` for a malformed pattern, whatever the path is.
- Every other character matches only itself.
- Path segments that start with `.` get no special treatment.

Matching is case-sensitive unless `ignore_case=True`. Then only the letters `a`-`z` and `A`-`Z`
are affected: such a letter in the pattern matches both of its cases, and such a letter in the
path is in a set when either of its cases is. Every other character is compared as before.

You may assume that both arguments are non-empty and have no empty segments, and that the
pattern contains no `\`.
