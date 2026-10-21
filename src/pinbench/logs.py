"""Logging: human-readable by default, one JSON object per line with PINBENCH_LOG_FORMAT=json."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

# Attributes every LogRecord has; anything else was passed via `extra=` and is structured context.
_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        extras = {k: v for k, v in record.__dict__.items() if k not in _RESERVED}
        suffix = " " + " ".join(f"{k}={v}" for k, v in extras.items()) if extras else ""
        base = f"{record.levelname.lower():<7} {record.name}: {record.getMessage()}{suffix}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure(level: str | None = None, fmt: str | None = None) -> None:
    """Configure the `pinbench` logger tree. Safe to call more than once."""
    level = (level or os.environ.get("PINBENCH_LOG_LEVEL", "INFO")).upper()
    fmt = (fmt or os.environ.get("PINBENCH_LOG_FORMAT", "text")).lower()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    root = logging.getLogger("pinbench")
    root.handlers[:] = [handler]
    root.setLevel(level)
    root.propagate = False
