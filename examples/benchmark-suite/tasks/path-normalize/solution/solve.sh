#!/bin/bash
cat > /app/pathnorm.py <<'EOF'
import string

_ALLOWED = frozenset(string.ascii_letters + string.digits + "._-")


def _scan(path: str) -> tuple[bool, list[str], bool, bool]:
    """Return (absolute, kept segments, names a directory, has a `..` that cancels no name).

    Raises ValueError for an invalid path.
    """
    absolute = path.startswith("/")
    pieces = path.split("/")
    kept: list[str] = []
    uncancelled = False
    for segment in pieces:
        if segment == "":
            continue
        if segment.startswith("-") or not _ALLOWED.issuperset(segment):
            raise ValueError(f"invalid path segment: {segment!r}")
        if segment == ".":
            continue
        if segment == "..":
            if kept and kept[-1] != "..":
                kept.pop()
            else:
                uncancelled = True
                if not absolute:
                    kept.append("..")
        else:
            kept.append(segment)
    directory = path != "" and pieces[-1] in ("", ".", "..")
    return absolute, kept, directory, uncancelled


def normalize(path: str) -> str:
    """Return the normalized form of a POSIX-style path."""
    absolute, kept, directory, _ = _scan(path)
    joined = (("/" if absolute else "") + "/".join(kept)) or "."
    if directory and not joined.endswith("/"):
        joined += "/"
    return joined


def is_within(root: str, path: str) -> bool:
    """Report whether `path` lies inside `root` (or is `root` itself)."""
    root_absolute, root_kept, _, root_uncancelled = _scan(root)
    path_absolute, path_kept, _, path_uncancelled = _scan(path)
    if root_absolute != path_absolute or root_uncancelled or path_uncancelled:
        return False
    return path_kept[: len(root_kept)] == root_kept
EOF
