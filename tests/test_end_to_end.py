"""The vertical slice through the CLI: suite -> run -> store -> compare -> report."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from agent_canary.cli import app
from agent_canary.config import load_config
from agent_canary.models import TrialRecord
from agent_canary.orchestrate import PinDriftError, run_compare
from agent_canary.runners import BatchRequest
from agent_canary.suite import load_suite
from tests.conftest import record

cli = CliRunner()


@pytest.fixture(autouse=True)
def _writable_bundles(simulated_project: Path) -> Any:
    """Sealed bundles are read-only; make them removable so tmp_path cleanup succeeds."""
    yield
    for root, _dirs, files in os.walk(simulated_project):
        Path(root).chmod(0o755)
        for f in files:
            (Path(root) / f).chmod(0o644)


def _invoke(*args: str) -> Any:
    return cli.invoke(app, list(args), catch_exceptions=False)


def test_validate(simulated_project: Path) -> None:
    result = _invoke("validate", "-c", str(simulated_project))
    assert result.exit_code == 0
    assert "6 tasks" in result.output
    assert "needs >= 7 discordant pairs" in result.output


def test_compare_detects_regression_and_writes_everything(simulated_project: Path) -> None:
    result = _invoke("compare", "good", "bad", "-c", str(simulated_project))
    assert result.exit_code == 1, result.output
    assert "REGRESSION" in result.output

    home = simulated_project / ".canary"
    (run_dir,) = (home / "runs").iterdir()
    verdict = json.loads((run_dir / "verdict.json").read_text())
    assert verdict["decision"] == "regression"
    assert verdict["stop_reason"] == "significant"
    assert verdict["batches_run"] < 15
    assert {m["metric"] for m in verdict["metrics"]} >= {"cost_usd", "agent_seconds"}

    report = home / "reports" / f"{run_dir.name}.html"
    html = report.read_text()
    assert "Regression detected" in html
    assert "task-0" in html

    assert _invoke("verify", run_dir.name[:20], "-c", str(simulated_project)).exit_code == 0
    listed = _invoke("runs", "-c", str(simulated_project)).output
    assert run_dir.name in listed
    assert "regression" in listed

    (home / "index.db").unlink()
    assert "indexed 1 runs" in _invoke("index", "rebuild", "-c", str(simulated_project)).output


def test_compare_same_pins_is_inconclusive(simulated_project: Path) -> None:
    result = _invoke(
        "compare", "good", "same", "-c", str(simulated_project), "--max-batches", "3", "--no-report"
    )
    assert result.exit_code == 0
    assert "INCONCLUSIVE" in result.output
    assert "stop=max_batches" in result.output


def test_dollar_budget_stops_the_loop(simulated_project: Path) -> None:
    # 6 tasks x 2 attempts x 2 arms x ~$0.40 is ~$4.80 per batch: after one batch the projected
    # spend (~$9.60) exceeds the $7 cap, so the loop stops before starting a second batch.
    result = _invoke(
        "compare", "good", "same", "-c", str(simulated_project), "--max-usd", "7", "--no-report"
    )
    assert "stop=budget_usd" in result.output
    assert "batches=1" in result.output


def test_single_run_and_rerender_report(simulated_project: Path) -> None:
    result = _invoke("run", "good", "-c", str(simulated_project), "--attempts", "2")
    assert result.exit_code == 0
    assert "/12 passed" in result.output
    run_id = result.output.split("run ", 1)[1].split(":", 1)[0]
    out = simulated_project / "custom.html"
    assert _invoke("report", run_id, "-c", str(simulated_project), "-o", str(out)).exit_code == 0
    assert "Trials (12)" in out.read_text()


def test_unknown_pin_is_a_clean_error(simulated_project: Path) -> None:
    result = cli.invoke(app, ["compare", "good", "nope", "-c", str(simulated_project)])
    assert result.exit_code == 2
    assert "unknown pin 'nope'" in result.output


class _DriftingRunner:
    """Reports a different installed version than the pin asked for."""

    def describe(self) -> dict[str, Any]:
        return {"kind": "fake"}

    def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
        return [
            record(task=t.name, pin=p, batch=request.batch, name=f"{t.name}-{p}", version="9.9.9")
            for t in request.tasks
            for p in request.pins
        ]


def test_pin_drift_aborts_and_still_seals_bundle(simulated_project: Path) -> None:
    loaded = load_config(simulated_project)
    with pytest.raises(PinDriftError, match=r"pinned 1\.0\.0, ran 9\.9\.9"):
        run_compare(loaded, load_suite(loaded), _DriftingRunner(), "good", "bad")
    (run_dir,) = (simulated_project / ".canary" / "runs").iterdir()
    assert (run_dir / "SHA256SUMS").exists()
    assert not (run_dir / "verdict.json").exists()
