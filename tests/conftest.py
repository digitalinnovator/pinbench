from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from agent_canary.models import TrialRecord, TrialStatus

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).parent.parent


def write_task(root: Path, name: str) -> Path:
    task = root / name
    (task / "environment").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "task.toml").write_text('schema_version = "1.4"\n')
    (task / "instruction.md").write_text(f"Do {name}.\n")
    (task / "environment" / "Dockerfile").write_text("FROM scratch\n")
    (task / "tests" / "test.sh").write_text("echo 1 > /logs/verifier/reward.txt\n")
    return task


@pytest.fixture
def simulated_project(tmp_path: Path) -> Path:
    """A throwaway canary project with 6 stub tasks and a simulated runner."""
    for i in range(6):
        write_task(tmp_path / "tasks", f"task-{i}")
    (tmp_path / "canary.toml").write_text(
        textwrap.dedent(
            """
            [suite]
            name = "test-suite"

            [runner]
            kind = "simulated"
            simulated_task_spread = 0.5

            [runner.simulated.good]
            pass_rate = 0.85
            cost_usd = 0.40

            [runner.simulated.bad]
            pass_rate = 0.30
            cost_usd = 0.60

            [runner.simulated.same]
            pass_rate = 0.85
            cost_usd = 0.40

            [stats]
            bootstrap_resamples = 500

            [budget]
            max_usd = 1000.0
            max_batches = 15
            attempts_per_batch = 2

            [pins.good]
            harness = "claude-code"
            version = "1.0.0"

            [pins.bad]
            harness = "claude-code"
            version = "1.0.1"

            [pins.same]
            harness = "claude-code"
            version = "1.0.2"
            """
        )
    )
    return tmp_path


def record(
    *,
    task: str = "t",
    pin: str = "a",
    batch: int = 0,
    status: TrialStatus = TrialStatus.PASS,
    name: str | None = None,
    cost: float | None = 0.1,
    version: str | None = None,
) -> TrialRecord:
    return TrialRecord(
        trial_name=name or f"{task}-{pin}-{batch}",
        task=task,
        pin=pin,
        batch=batch,
        status=status,
        reward={TrialStatus.PASS: 1.0, TrialStatus.FAIL: 0.0}.get(status),
        reported_cost_usd=cost,
        installed_version=version,
        version_source="trajectory" if version else None,
    )
