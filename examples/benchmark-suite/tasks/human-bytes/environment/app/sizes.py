def format_size(n: int) -> str:
    """Render a byte count such as 1536 as '1.5 KiB'."""
    raise NotImplementedError


def parse_size(text: str) -> int:
    """Read a rendered size such as '1.5 KiB' back into a byte count."""
    raise NotImplementedError
