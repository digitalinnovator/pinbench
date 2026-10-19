#!/bin/bash
# Careless solution: right about slashes, dot segments, directories and the allowed characters,
# quick about `is_within`. It answers False for an absolute path against a relative one before
# it has checked either argument, and it looks for a `..` among the kept segments, which misses
# a `..` that an absolute path dropped.
cat > /app/pathnorm.py <<'EOF'
import re

_NAME = re.compile(r"[A-Za-z0-9._-]+")


def _kept_segments(path: str, absolute: bool) -> list[str]:
    kept: list[str] = []
    for segment in path.split("/"):
        if segment == "":
            continue
        if segment.startswith("-") or not _NAME.fullmatch(segment):
            raise ValueError(f"invalid segment: {segment!r}")
        if segment == ".":
            continue
        if segment == "..":
            if kept and kept[-1] != "..":
                kept.pop()
            elif not absolute:
                kept.append("..")
        else:
            kept.append(segment)
    return kept


def normalize(path: str) -> str:
    """Return the normalized form of a POSIX-style path."""
    absolute = path.startswith("/")
    kept = _kept_segments(path, absolute)
    result = ("/" if absolute else "") + "/".join(kept)
    if not result:
        result = "."
    last = path.rsplit("/", 1)[-1]
    if (path.endswith("/") or last in (".", "..")) and not result.endswith("/"):
        result += "/"
    return result


def is_within(root: str, path: str) -> bool:
    """Report whether `path` lies inside `root` (or is `root` itself)."""
    root_absolute = root.startswith("/")
    path_absolute = path.startswith("/")
    if root_absolute != path_absolute:
        return False
    root_kept = _kept_segments(root, root_absolute)
    path_kept = _kept_segments(path, path_absolute)
    if ".." in root_kept or ".." in path_kept:
        return False
    return path_kept[: len(root_kept)] == root_kept
EOF
