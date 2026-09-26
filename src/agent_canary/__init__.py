"""Agent Canary: detect when a coding-agent harness or model update makes it worse or pricier."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("agent-canary")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
