"""The vertical slice through the CLI: suite -> run -> store -> compare -> report."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from pinbench.cli import app
from pinbench.config import load_config
from pinbench.models import TrialRecord
from pinbench.orchestrate import PinDriftError, run_compare
from pinbench.pricing import load_price_table
from pinbench.report import render_report
from pinbench.runners import BatchRequest
from pinbench.runners.simulated import SimulatedRunner
from pinbench.store import RunIndex
from pinbench.suite import load_suite
from pinbench.verifier import check_trial
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
    assert "needs >= 10 discordant pairs" in result.output


def test_compare_detects_regression_and_writes_everything(simulated_project: Path) -> None:
    result = _invoke("compare", "good", "bad", "-c", str(simulated_project))
    assert result.exit_code == 1, result.output
    assert "REGRESSION" in result.output

    home = simulated_project / ".pinbench"
    (run_dir,) = (home / "runs").iterdir()
    verdict = json.loads((run_dir / "verdict.json").read_text())
    assert verdict["decision"] == "regression"
    assert verdict["stop_reason"] == "significant"
    assert verdict["batches_run"] < 15
    assert {m["metric"] for m in verdict["metrics"]} >= {"cost_usd", "agent_seconds"}
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["settings"]["pricing"]["version"] == load_price_table().version
    assert len(manifest["settings"]["pricing"]["sha256"]) == 64

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
    assert "(of 12)" in result.output
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
    (run_dir,) = (simulated_project / ".pinbench" / "runs").iterdir()
    assert (run_dir / "SHA256SUMS").exists()
    assert not (run_dir / "verdict.json").exists()


class _EchoingRunner(_DriftingRunner):
    """Reports a mismatched version only as the runner's echo, with no transcript proof."""

    def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
        return [
            r.model_copy(update={"version_source": "runner"}) for r in super().run_batch(request)
        ]


def test_drift_needs_transcript_proof(simulated_project: Path) -> None:
    loaded = load_config(simulated_project)
    outcome = run_compare(
        loaded, load_suite(loaded), _EchoingRunner(), "good", "bad", max_batches=1
    )
    assert outcome.verdict is not None


class _ClaimingRunner:
    """Writes a transcript per trial: `good` tests before claiming, `bad` claims without testing."""

    def describe(self) -> dict[str, Any]:
        return {"kind": "fake"}

    def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
        out = []
        for t in request.tasks:
            for p in request.pins:
                rel = Path("harbor") / f"batch-{request.batch:03d}" / f"{t.name}__{p}"
                steps: list[dict[str, Any]] = [
                    {
                        "step_id": 1,
                        "source": "agent",
                        "message": "",
                        "tool_calls": [
                            {"tool_call_id": "e", "function_name": "Edit", "arguments": {}}
                        ],
                    }
                ]
                if p == "good":
                    steps.append(
                        {
                            "step_id": 2,
                            "source": "agent",
                            "message": "",
                            "tool_calls": [
                                {
                                    "tool_call_id": "t",
                                    "function_name": "Bash",
                                    "arguments": {"command": "pytest -q | tail -3"},
                                }
                            ],
                            "observation": {
                                "results": [{"source_call_id": "t", "content": "3 passed in 0.1s"}]
                            },
                        }
                    )
                steps.append({"step_id": 3, "source": "agent", "message": "All tests pass."})
                agent_dir = request.bundle_dir / rel / "agent"
                agent_dir.mkdir(parents=True)
                (agent_dir / "trajectory.json").write_text(json.dumps({"steps": steps}))
                rec = record(task=t.name, pin=p, batch=request.batch, name=f"{t.name}__{p}")
                out.append(
                    rec.model_copy(
                        update={
                            "trial_dir": rel.as_posix(),
                            "claim_check": check_trial(request.bundle_dir / rel),
                        }
                    )
                )
        return out


def test_false_success_reaches_verdict_report_index_and_cli(simulated_project: Path) -> None:
    loaded = load_config(simulated_project)
    outcome = run_compare(
        loaded, load_suite(loaded), _ClaimingRunner(), "good", "bad", max_batches=1
    )
    verdict = outcome.verdict
    assert verdict is not None
    assert (verdict.baseline.checked, verdict.baseline.claims, verdict.baseline.false_success) == (
        6,
        6,
        0,
    )
    assert (verdict.candidate.claims, verdict.candidate.false_success) == (6, 6)

    html = render_report(outcome.bundle, simulated_project / "r.html").read_text()
    assert "false success" in html
    assert "no test run after last edit" in html

    index = RunIndex(simulated_project / ".pinbench" / "index.db")
    with index._connect() as db:
        rows = db.execute(
            "SELECT pin, claim_check, COUNT(*) FROM trials GROUP BY 1, 2 ORDER BY 1"
        ).fetchall()
    assert [tuple(r) for r in rows] == [("bad", "false_success", 6), ("good", "supported", 6)]

    result = _invoke("claims", outcome.bundle.run_id, "-c", str(simulated_project))
    assert result.exit_code == 0
    assert "12 transcripts checked" in result.output
    assert "false success 6" in result.output
    assert "no_test_run_after_last_edit" in result.output


def test_warmup_batches_are_left_out_of_cost_metrics_only(simulated_project: Path) -> None:
    toml = simulated_project / "pinbench.toml"
    toml.write_text(toml.read_text().replace("[stats]", "[stats]\nwarmup_batches = 1"))
    loaded = load_config(simulated_project)
    cfg = loaded.config
    runner = SimulatedRunner(
        cfg.runner.simulated, seed=cfg.stats.seed, task_spread=cfg.runner.simulated_task_spread
    )
    verdict = run_compare(loaded, load_suite(loaded), runner, "good", "same", max_batches=3).verdict
    assert verdict is not None
    assert verdict.metrics_from_batch == 1
    assert verdict.n_pairs == 36  # 6 tasks x 2 attempts x 3 batches: pass rate uses every batch
    cost = next(m for m in verdict.metrics if m.metric == "cost_usd")
    assert cost.n_baseline == 24  # batches 1 and 2 only


def test_continuing_a_run_gives_the_verdict_of_one_longer_run(simulated_project: Path) -> None:
    loaded = load_config(simulated_project)
    cfg = loaded.config

    def runner() -> SimulatedRunner:
        return SimulatedRunner(
            cfg.runner.simulated, seed=cfg.stats.seed, task_spread=cfg.runner.simulated_task_spread
        )

    suite = load_suite(loaded)
    whole = run_compare(loaded, suite, runner(), "good", "same", max_batches=4).verdict
    first = run_compare(loaded, suite, runner(), "good", "same", max_batches=2)
    rest = run_compare(
        loaded, suite, runner(), "good", "same", max_batches=2, continue_from=first.bundle
    )
    assert whole is not None
    assert rest.verdict is not None
    # The simulated runner draws batch b from the same seed either way, so the trials are the
    # same, and so must be the e-process.
    assert [p.batch for p in rest.verdict.history] == [0, 1, 2, 3]
    assert rest.verdict.e_value == pytest.approx(whole.e_value)
    assert rest.verdict.p_value == pytest.approx(whole.p_value)
    assert (rest.verdict.n_regress, rest.verdict.n_improve) == (whole.n_regress, whole.n_improve)
    assert rest.verdict.spent_usd == pytest.approx(whole.spent_usd)
    assert rest.bundle.manifest().continues == first.bundle.run_id
    assert len(rest.bundle.trials()) == len(first.bundle.trials())  # only the new batches


def test_a_run_can_only_continue_unchanged(simulated_project: Path) -> None:
    loaded = load_config(simulated_project)
    cfg = loaded.config
    runner = SimulatedRunner(
        cfg.runner.simulated, seed=cfg.stats.seed, task_spread=cfg.runner.simulated_task_spread
    )
    suite = load_suite(loaded)
    first = run_compare(loaded, suite, runner, "good", "same", max_batches=1)
    with pytest.raises(ValueError, match="it compared good with same"):
        run_compare(loaded, suite, runner, "good", "bad", continue_from=first.bundle)
    flagged = run_compare(loaded, suite, runner, "good", "bad")
    assert flagged.verdict is not None
    assert flagged.verdict.stop_reason == "significant"
    with pytest.raises(ValueError, match="stopped for 'significant', which is final"):
        run_compare(loaded, suite, runner, "good", "bad", continue_from=flagged.bundle)
    toml = simulated_project / "pinbench.toml"
    toml.write_text(toml.read_text().replace('version = "1.0.2"', 'version = "1.0.3"'))
    changed = load_config(simulated_project)
    with pytest.raises(ValueError, match="pin 'same' has changed since"):
        run_compare(changed, suite, runner, "good", "same", continue_from=first.bundle)
