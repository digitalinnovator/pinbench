"""Content hashing for tasks, pins and bundle files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_IGNORED_NAMES = {".DS_Store", "__pycache__", ".pytest_cache", ".git"}
_CHUNK = 1 << 20


def canonical_json(value: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace variation, UTF-8 preserved."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path) -> list[Path]:
    """All regular files under root, sorted, skipping caches and VCS metadata."""
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and not any(part in _IGNORED_NAMES for part in p.relative_to(root).parts)
    )


def sha256_tree(root: Path) -> str:
    """Hash a directory by relative path and content, so renames and edits both change it."""
    h = hashlib.sha256()
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        h.update(rel.encode("utf-8") + b"\0")
        h.update(sha256_file(path).encode("ascii") + b"\n")
    return h.hexdigest()
