def normalize(path: str) -> str:
    """Return the normalized form of a POSIX-style path."""
    raise NotImplementedError


def is_within(root: str, path: str) -> bool:
    """Report whether `path` lies inside `root` (or is `root` itself)."""
    raise NotImplementedError
