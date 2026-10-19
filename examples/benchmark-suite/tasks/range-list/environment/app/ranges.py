"""Compress integers into range text such as '1-3,5,7-9', and expand it back."""

from collections.abc import Iterable


def compress(numbers: Iterable[int]) -> str:
    """Return the range text for the given integers."""
    raise NotImplementedError


def expand(text: str) -> list[int]:
    """Return the integers that the range text stands for."""
    raise NotImplementedError
