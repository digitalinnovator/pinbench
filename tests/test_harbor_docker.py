"""Real Harbor trials in Docker (marker: docker). Zero cost: oracle and nop agents only.

Needs Docker and the tools/harbor environment (`make dev`). Proves the whole slice against the
real execution layer: the generated JobConfig is accepted, both arms run in one Harbor job, trials
map back to pins, and the e-process flags nop as a regression against oracle.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from agent_canary.config import load_config
from agent_canary.orchestrate import run_compare
from agent_canary.runners.harbor import HarborRunner
from agent_canary.suite import load_suite
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.docker


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True, check=False).returncode == 0


@pytest.fixture
def demo_project(tmp_path: Path) -> Any:
    if not _docker_available():
        pytest.skip("docker is not available")
    project = tmp_path / "demo"
    shutil.copytree(
        REPO_ROOT / "examples" / "demo-suite", project, ignore=shutil.ignore_patterns(".canary")
    )
    config = (project / "canary.toml").read_text()
    config = config.replace('"../../tools/harbor"', f'"{REPO_ROOT / "tools" / "harbor"}"')
    (project / "canary.toml").write_text(config)
    yield project
    for root, _dirs, files in os.walk(project):
        Path(root).chmod(0o755)
        for f in files:
            (Path(root) / f).chmod(0o644)


def test_oracle_vs_nop_is_flagged_through_real_harbor(demo_project: Path) -> None:
    loaded = load_config(demo_project)
    runner = HarborRunner(loaded.config.runner, cwd=loaded.root, pass_threshold=1.0)
    outcome = run_compare(loaded, load_suite(loaded), runner, "oracle", "nop", max_batches=5)
    verdict = outcome.verdict
    assert verdict is not None

    # 3 tasks per batch, all pairs discordant; with q_max = 0.8, E crosses 20 at 10 pairs (batch 4).
    assert verdict.decision == "regression"
    assert verdict.batches_run == 4
    assert (verdict.baseline.passes, verdict.baseline.n) == (12, 12)
    assert (verdict.candidate.passes, verdict.candidate.n) == (0, 12)
    assert verdict.dropped_pairs == 0

    manifest = outcome.bundle.manifest()
    assert manifest.runner["harbor_version"] == "0.23.0"
    assert outcome.bundle.verify() == []
    trial_dirs = {t.trial_dir for t in outcome.bundle.trials()}
    assert all(d and (outcome.bundle.path / d / "result.json").exists() for d in trial_dirs)
