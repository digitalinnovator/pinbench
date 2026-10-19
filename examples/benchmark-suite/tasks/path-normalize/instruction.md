Implement `normalize(path: str) -> str` and `is_within(root: str, path: str) -> bool` in
`/app/pathnorm.py`. Both treat POSIX-style paths as plain strings and never touch the file
system. `/app/test_pathnorm.py` holds a small test (`python -m pytest -q`).

Rules for `normalize`:

- A path is absolute when it starts with `/`; otherwise it is relative.
- A run of one or more slashes is one separator, wherever it occurs in the path. The segments
  are the non-empty pieces between separators.
- A `.` segment is never kept. A `..` segment cancels the nearest ordinary name still kept to
  its left, so neither is kept; with no such name, it is dropped in an absolute path and kept
  in a relative path.
- Every other segment (such as `...`, `.git` or `a-b`) is an ordinary name and is kept unchanged.
- A path is invalid when any segment, whether or not it is kept, starts with `-` or contains a
  character other than an ASCII letter, an ASCII digit, `.`, `_` or `-`. `normalize` raises
  `ValueError` for an invalid path.
- The joined form is the kept segments joined by single slashes, after a leading `/` for an
  absolute path. For a relative path with no kept segments it is `.`, not the empty string.
- A path names a directory when it ends with `/` or its last segment is `.` or `..`. For a
  directory the result is the joined form made to end with exactly one `/`; for any other path
  it is the joined form itself.

Rules for `is_within`, where kept segments are those `normalize` keeps:

- It raises `ValueError` when either argument is invalid, whatever the rules below would give.
- It is false when one argument is absolute and the other relative, and when either argument
  has a `..` segment that cancels no name.
- Otherwise it is true exactly when the kept segments of `root` are a prefix of the kept
  segments of `path`, compared segment by segment. Equal paths count as within.
