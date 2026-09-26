"""Execution back-ends. The canary never runs agents itself (ADR-0002)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agent_canary.config import PinSpec
from agent_canary.models import TrialRecord
from agent_canary.suite import TaskRef


@dataclass(frozen=True)
class BatchRequest:
    """One full sweep: every task, `attempts` times, for every pin (ADR-0003)."""

    batch: int
    tasks: tuple[TaskRef, ...]
    pins: dict[str, PinSpec]
    attempts: int
    bundle_dir: Path


class Runner(Protocol):
    def describe(self) -> dict[str, Any]:
        """Identity and version of the back-end, recorded in the run manifest."""
        ...

    def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
        """Run one batch to completion and return one record per trial."""
        ...


class RunnerError(RuntimeError):
    pass
