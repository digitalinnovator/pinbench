"""Execution back-ends. pinbench never runs agents itself (ADR-0002)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pinbench.config import PinSpec
from pinbench.models import TrialRecord
from pinbench.suite import TaskRef


@dataclass(frozen=True)
class BatchRequest:
    """One full sweep: every task, `attempts` times, for every pin (ADR-0003)."""

    batch: int
    tasks: tuple[TaskRef, ...]
    pins: dict[str, PinSpec]
    attempts: int
    bundle_dir: Path


class Runner(Protocol):
    """A runner that calls paid APIs also sets `spends_money = True` (read with getattr).

    It may also define `validate(pins)`, called before anything is reserved or created, to
    reject a run it could never start.
    """

    def describe(self) -> dict[str, Any]:
        """Identity and version of the back-end, recorded in the run manifest."""
        ...

    def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
        """Run one batch to completion and return one record per trial."""
        ...


class RunnerError(RuntimeError):
    pass


class RunnerNotStarted(RunnerError):  # noqa: N818  (reads as a state, like StopIteration)
    """A batch failed before any trial could start, so it cannot have spent anything."""
