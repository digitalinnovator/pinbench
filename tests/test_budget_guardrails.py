"""Spending guardrails (ADR-0009): the ledger, cap-priced reservations, and the early stops."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from agent_canary.budget import BudgetError
from agent_canary.cli import app
from agent_canary.config import PinSpec, load_config
from agent_canary.ledger import Ledger, LedgerError
from agent_canary.models import TrialRecord, TrialStatus
from agent_canary.orchestrate import run_compare, run_single
from agent_canary.runners import BatchRequest, RunnerError
from agent_canary.suite import load_suite
from tests.conftest import record

cli = CliRunner()

CAPPED = """
[pins.base]
harness = "claude-code"
version = "1.0.0"
model = "anthropic/claude-sonnet-5"
options = { max_budget_usd = "0.20" }

[pins.cand]
harness = "claude-code"
version = "1.0.0"
model = "anthropic/claude-sonnet-5"
options = { max_budget_usd = "0.20", reasoning_effort = "low" }

[pins.uncapped]
harness = "claude-code"
version = "1.0.0"
model = "anthropic/claude-sonnet-5"

[pins.codex]
harness = "codex"
version = "0.159.2"
model = "openai/gpt-6-luna"
timeout_sec = 120
reserve_usd = 0.30
"""
# Per trial: the $0.20 harness cap plus one in-flight request at Sonnet 5 prices
# (20k tokens written to a cold cache at $2.50/M + 4k output at $10/M = $0.09).
CAP = 0.20 + 0.09
BATCH_WORST = 6 * 2 * 2 * CAP  # 6 tasks x 2 attempts x 2 pins


@pytest.fixture
def project(simulated_project: Path) -> Any:
    toml = simulated_project / "canary.toml"
    toml.write_text(toml.read_text() + CAPPED)
    yield simulated_project
    for root, _dirs, files in os.walk(simulated_project):
        Path(root).chmod(0o755)
        for f in files:
            (Path(root) / f).chmod(0o644)


class PaidRunner:
    """A fake runner that claims to spend money, with scripted outcomes per batch."""

    spends_money = True

    def __init__(
        self,
        *,
        cost: float | None = 0.05,
        candidate_status: TrialStatus = TrialStatus.FAIL,
        error_pin: str | None = None,
        crash_on_batch: int | None = None,
        drop_trials: int = 0,
    ) -> None:
        self.cost = cost
        self.candidate_status = candidate_status
        self.error_pin = error_pin
        self.crash_on_batch = crash_on_batch
        self.drop_trials = drop_trials
        self.batches = 0

    def describe(self) -> dict[str, Any]:
        return {"kind": "fake-paid"}

    def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
        self.batches += 1
        if self.crash_on_batch == request.batch:
            raise RunnerError("harbor fell over")
        out = []
        for t in request.tasks:
            for i, pin in enumerate(request.pins):
                for attempt in range(request.attempts):
                    status = TrialStatus.PASS if i == 0 else self.candidate_status
                    if pin == self.error_pin:
                        status = TrialStatus.ERROR
                    out.append(
                        record(
                            task=t.name,
                            pin=pin,
                            batch=request.batch,
                            status=status,
                            cost=self.cost,
                            name=f"{t.name}-{pin}-{request.batch}-{attempt}",
                        )
                    )
        return out[: len(out) - self.drop_trials]


def _compare(project: Path, runner: PaidRunner, **kw: Any) -> Any:
    loaded = load_config(project)
    return run_compare(loaded, load_suite(loaded), runner, "base", "cand", **kw)


# -- ledger -----------------------------------------------------------------------------------


def test_ledger_reserve_settle_and_refuse(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    with pytest.raises(LedgerError, match="no spending limit"):
        ledger.reserve("anthropic", 1.0, run_id="r", batch=0)
    ledger.set_limit("anthropic", 10.0)
    first = ledger.reserve("anthropic", 6.0, run_id="r", batch=0)
    assert ledger.status("anthropic").reserved_usd == 6.0
    with pytest.raises(LedgerError, match="refuses this batch"):
        ledger.reserve("anthropic", 6.0, run_id="r", batch=1)  # 6 held + 6 > 10
    ledger.settle(first, 2.5)
    status = ledger.status("anthropic")
    assert (status.settled_usd, status.reserved_usd, status.remaining_usd) == (2.5, 0.0, 7.5)
    ledger.reserve("anthropic", 7.5, run_id="r", batch=1)  # exactly what is left fits
    assert ledger.status("openai").limit_usd is None  # pools are independent


def test_ledger_release_is_per_run_and_refuses_a_batch_that_may_still_run(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    ledger.set_limit("anthropic", 20.0)
    ledger.reserve("anthropic", 4.0, run_id="crashed", batch=0)
    ledger.reserve("anthropic", 4.0, run_id="crashed", batch=1)
    ledger.reserve("anthropic", 6.0, run_id="running", batch=0)
    assert [e["run_id"] for e in ledger.open_reservations("anthropic")] == [
        "crashed",
        "crashed",
        "running",
    ]
    with pytest.raises(LedgerError, match="no open reservation for run 'typo'"):
        ledger.release("anthropic", "typo", 0.0, "n")
    with pytest.raises(LedgerError, match="may still be running"):
        ledger.release("anthropic", "crashed", 1.25, "n", min_age_sec=3600)
    released = ledger.release("anthropic", "crashed", 1.25, "console says 1.25")
    assert len(released) == 2
    status = ledger.status("anthropic")
    # The other run's live reservation is untouched.
    assert (status.settled_usd, status.reserved_usd) == (1.25, 6.0)
    assert ledger.correct("anthropic", 0.75, "console says 2.00").settled_usd == 2.0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_ledger_refuses_amounts_that_would_switch_the_limit_off(tmp_path: Path, bad: float) -> None:
    ledger = Ledger(tmp_path)
    ledger.set_limit("anthropic", 10.0)
    for call in (
        lambda: ledger.set_limit("anthropic", bad),
        lambda: ledger.correct("anthropic", bad, "n"),
        lambda: ledger.reserve("anthropic", bad, run_id="r", batch=0),
    ):
        with pytest.raises(LedgerError):
            call()
    assert ledger.status("anthropic").limit_usd == 10.0
    # A non-finite number written into the file by hand stops spending instead of enabling it.
    with (tmp_path / "anthropic.jsonl").open("a") as f:
        f.write('{"type": "correct", "pool": "anthropic", "usd": NaN}\n')
    with pytest.raises(LedgerError, match="finite"):
        ledger.reserve("anthropic", 1.0, run_id="r", batch=0)


def test_ledger_survives_a_torn_last_line_by_refusing_not_by_forgetting(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    ledger.set_limit("anthropic", 10.0)
    with (tmp_path / "anthropic.jsonl").open("a") as f:
        f.write('{"type": "reserve", "id": "abc", "usd": 4')  # a crash mid-write
    with pytest.raises(LedgerError, match="not valid JSON"):
        ledger.status("anthropic")
    # Once the operator removes the torn line, later records are intact.
    path = tmp_path / "anthropic.jsonl"
    path.write_text(path.read_text().rsplit("\n", 1)[0])  # no trailing newline left behind
    ledger.correct("anthropic", 1.0, "n")
    assert ledger.status("anthropic").settled_usd == 1.0


def test_limit_if_unset_never_resets_an_existing_limit(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    assert ledger.set_limit("anthropic", 20.0, if_unset=True).limit_usd == 20.0
    assert ledger.set_limit("anthropic", 99.0, if_unset=True).limit_usd == 20.0


def test_lowering_the_limit_below_spend_stops_everything(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path)
    ledger.set_limit("anthropic", 10.0)
    ledger.settle(ledger.reserve("anthropic", 5.0, run_id="r", batch=0), 5.0)
    ledger.set_limit("anthropic", 4.0)
    with pytest.raises(LedgerError):
        ledger.reserve("anthropic", 0.01, run_id="r", batch=1)


# -- pins -------------------------------------------------------------------------------------


def _cc(**kw: Any) -> PinSpec:
    return PinSpec(harness="claude-code", version="1", model="anthropic/claude-sonnet-5", **kw)


def test_pin_caps_and_pools() -> None:
    capped = _cc(options={"max_budget_usd": "0.20"})
    assert (capped.pool(), capped.trial_cap_usd(0.05)) == ("anthropic", pytest.approx(0.25))
    assert PinSpec(harness="codex", version="1").pool() == "openai"
    assert PinSpec(harness="oracle").trial_cap_usd(0.05) == 0.0
    assert PinSpec(harness="oracle").pool() is None
    # reserve_usd is bookkeeping and does not change what runs, so not the fingerprint either.
    with_reserve = capped.model_copy(update={"reserve_usd": 9.0})
    assert with_reserve.fingerprint(Path()) == capped.fingerprint(Path())
    timed = capped.model_copy(update={"timeout_sec": 120.0})
    assert timed.fingerprint(Path()) != capped.fingerprint(Path())


def test_a_reservation_is_only_a_bound_if_something_enforces_it() -> None:
    # reserve_usd can raise the reservation above the harness cap, never lower it.
    assert _cc(options={"max_budget_usd": "1.00"}, reserve_usd=0.05).trial_cap_usd(0.05) == 1.05
    assert _cc(options={"max_budget_usd": "1.00"}, reserve_usd=2.0).trial_cap_usd(0.05) == 2.0
    # Claude Code without its own cap is unbounded, whatever is reserved.
    assert _cc(reserve_usd=0.10).trial_cap_usd(0.05) is None
    # A harness with no dollar cap needs a timeout AND a reservation.
    codex = {"harness": "codex", "version": "1", "model": "openai/gpt-6-luna"}
    assert PinSpec(**codex, reserve_usd=0.3).trial_cap_usd(0.05) is None
    assert PinSpec(**codex, timeout_sec=120).trial_cap_usd(0.05) is None
    assert PinSpec(**codex, timeout_sec=120, reserve_usd=0.3).trial_cap_usd(0.05) == 0.3


def test_pin_config_rejects_caps_that_would_not_hold() -> None:
    with pytest.raises(ValueError, match="greater than 0"):
        _cc(options={"max_budget_usd": "1.00"}, reserve_usd=0)
    with pytest.raises(ValueError, match="is a Claude Code flag"):
        PinSpec(harness="codex", version="1", options={"max_budget_usd": "0.10"})
    for bad in (0.20, "0", "-1", "nan", "inf", "cheap"):
        with pytest.raises(ValueError, match="must be a string holding a positive number"):
            _cc(options={"max_budget_usd": bad})


def test_a_model_missing_from_the_price_table_needs_an_explicit_reservation(
    project: Path,
) -> None:
    from agent_canary.budget import pin_cap_usd

    loaded = load_config(project)
    unknown = PinSpec(
        harness="claude-code",
        version="1",
        model="anthropic/claude-next",
        options={"max_budget_usd": "0.20"},
    )
    assert pin_cap_usd(loaded, unknown) is None
    assert pin_cap_usd(loaded, unknown.model_copy(update={"reserve_usd": 0.5})) == 0.5
    # Opus requests cost more than Sonnet ones, so the same cap reserves more.
    opus = _cc(options={"max_budget_usd": "0.20"}).model_copy(
        update={"model": "anthropic/claude-opus-5"}
    )
    assert pin_cap_usd(loaded, opus) == pytest.approx(0.20 + 0.225)
    assert pin_cap_usd(loaded, loaded.pin("base")) == pytest.approx(CAP)
    assert pin_cap_usd(loaded, loaded.pin("codex")) == 0.30


# -- compare ----------------------------------------------------------------------------------


def test_paid_run_is_refused_without_a_limit_and_nothing_is_created(project: Path) -> None:
    runner = PaidRunner()
    with pytest.raises(BudgetError, match="no spending limit is set for the 'anthropic' pool"):
        _compare(project, runner)
    assert runner.batches == 0
    assert not (project / ".canary" / "runs").exists()


def test_paid_pin_without_a_cap_is_refused(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    loaded = load_config(project)
    runner = PaidRunner()
    with pytest.raises(BudgetError, match="'uncapped' has no enforced per-trial spending bound"):
        run_compare(loaded, load_suite(loaded), runner, "base", "uncapped")
    assert runner.batches == 0


def test_first_batch_must_fit_the_ledger(project: Path) -> None:
    Ledger().set_limit("anthropic", BATCH_WORST - 0.01)
    runner = PaidRunner()
    with pytest.raises(BudgetError, match="one batch could cost"):
        _compare(project, runner)
    assert runner.batches == 0


def test_batches_reserve_the_worst_case_and_settle_to_actual(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    outcome = _compare(project, PaidRunner(cost=0.05), max_batches=2, max_usd=100.0)
    verdict = outcome.verdict
    # 6 tasks x 2 attempts: the candidate fails every pair, so the first batch already flags.
    assert (verdict.decision, verdict.stop_reason, verdict.batches_run) == (
        "regression",
        "significant",
        1,
    )
    status = Ledger().status("anthropic")
    assert status.settled_usd == pytest.approx(24 * 0.05)
    assert status.reserved_usd == 0.0
    entries = [
        json.loads(line)
        for line in (Ledger().directory / "anthropic.jsonl").read_text().splitlines()
    ]
    reserve = next(e for e in entries if e["type"] == "reserve")
    assert reserve["usd"] == pytest.approx(BATCH_WORST)
    assert reserve["run_id"] == outcome.bundle.run_id


def test_ledger_stops_a_run_between_batches(project: Path) -> None:
    # Room for two worst-case batches once the first has settled at its small real cost.
    Ledger().set_limit("anthropic", BATCH_WORST + 24 * 0.05 + 0.01)
    runner = PaidRunner(cost=0.05, candidate_status=TrialStatus.PASS)
    verdict = _compare(project, runner, max_batches=5, max_usd=100.0).verdict
    assert (verdict.stop_reason, verdict.batches_run) == ("ledger", 2)
    assert runner.batches == 2
    assert Ledger().status("anthropic").committed_usd == pytest.approx(48 * 0.05)


def test_a_crashed_batch_stays_reserved_at_its_worst_case(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    runner = PaidRunner(cost=0.05, candidate_status=TrialStatus.PASS, crash_on_batch=1)
    with pytest.raises(RunnerError):
        _compare(project, runner, max_batches=5, max_usd=100.0)
    status = Ledger().status("anthropic")
    assert status.settled_usd == pytest.approx(24 * 0.05)
    assert status.reserved_usd == pytest.approx(BATCH_WORST)


def test_unknown_costs_are_charged_at_the_cap_and_still_stop_the_run(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    runner = PaidRunner(cost=None, candidate_status=TrialStatus.PASS)
    verdict = _compare(project, runner, max_batches=10, max_usd=10.0).verdict
    # Each batch is charged 24 x $0.29 = $6.96: after one batch, 6.96 + 6.96 > 10 stops the run.
    assert (verdict.stop_reason, verdict.batches_run) == ("budget_usd", 1)
    assert verdict.spent_usd == pytest.approx(BATCH_WORST)
    assert verdict.cost_known is False
    assert Ledger().status("anthropic").settled_usd == pytest.approx(BATCH_WORST)


def test_missing_trials_are_settled_at_the_cap(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    runner = PaidRunner(cost=0.05, candidate_status=TrialStatus.PASS, drop_trials=2)
    _compare(project, runner, max_batches=1, max_usd=100.0)
    assert Ledger().status("anthropic").settled_usd == pytest.approx(22 * 0.05 + 2 * CAP)


def test_a_dead_arm_stops_the_run_after_one_batch(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    runner = PaidRunner(cost=None, error_pin="cand")
    verdict = _compare(project, runner, max_batches=10, max_usd=100.0).verdict
    assert (verdict.decision, verdict.stop_reason, verdict.batches_run) == (
        "inconclusive",
        "dead_batch",
        1,
    )
    assert runner.batches == 1


def test_futility_look_stops_a_run_that_is_going_nowhere(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    toml = project / "canary.toml"
    toml.write_text(toml.read_text().replace("[stats]", "[stats]\nfutility_after_batches = 2"))
    runner = PaidRunner(cost=0.01, candidate_status=TrialStatus.PASS)
    verdict = _compare(project, runner, max_batches=6, max_usd=100.0).verdict
    assert (verdict.decision, verdict.stop_reason, verdict.batches_run) == (
        "inconclusive",
        "futility",
        2,
    )


def test_futility_needs_a_one_sided_test(project: Path) -> None:
    toml = project / "canary.toml"
    toml.write_text(
        toml.read_text().replace(
            "[stats]", '[stats]\nfutility_after_batches = 2\nalternative = "two-sided"'
        )
    )
    with pytest.raises(ValueError, match="futility_after_batches needs"):
        load_config(project)


# -- run and the command line -------------------------------------------------------------------


def test_single_run_is_capped_and_charged(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    loaded = load_config(project)
    suite = load_suite(loaded)
    with pytest.raises(BudgetError, match="more than max_usd"):
        run_single(loaded, suite, PaidRunner(), "base", attempts=1, max_usd=1.0)  # worst $1.74
    run_single(loaded, suite, PaidRunner(cost=0.05), "base", attempts=1, max_usd=2.0)
    assert Ledger().status("anthropic").settled_usd == pytest.approx(6 * 0.05)


def test_compare_refuses_when_one_batch_could_pass_max_usd(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    runner = PaidRunner()
    with pytest.raises(
        BudgetError, match=r"one batch could cost .6\.96 .* more than max_usd .5\.00"
    ):
        _compare(project, runner, max_usd=5.0)
    assert runner.batches == 0


def test_a_batch_that_never_started_releases_its_reservation(project: Path) -> None:
    from agent_canary.runners import RunnerNotStarted

    class Unstartable(PaidRunner):
        def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
            raise RunnerNotStarted("harbor CLI not found")

    Ledger().set_limit("anthropic", 100.0)
    with pytest.raises(RunnerNotStarted):
        _compare(project, Unstartable(), max_usd=100.0)
    status = Ledger().status("anthropic")
    assert (status.settled_usd, status.reserved_usd) == (0.0, 0.0)


def test_a_runner_can_reject_a_run_before_anything_is_reserved(project: Path) -> None:
    class Picky(PaidRunner):
        def validate(self, pins: dict[str, PinSpec]) -> None:
            raise RunnerError("pins differ only in config files")

    Ledger().set_limit("anthropic", 100.0)
    runner = Picky()
    with pytest.raises(RunnerError, match="differ only"):
        _compare(project, runner, max_usd=100.0)
    assert runner.batches == 0
    assert not (project / ".canary" / "runs").exists()
    assert Ledger().open_reservations("anthropic") == []


def test_errors_charged_at_the_cap_mark_the_spend_as_an_upper_bound(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)

    class HalfDead(PaidRunner):
        def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
            return [
                r.model_copy(update={"reported_cost_usd": None}) if r.pin == "cand" else r
                for r in super().run_batch(request)
            ]

    verdict = _compare(project, HalfDead(cost=0.05, error_pin="cand"), max_usd=100.0).verdict
    assert verdict.stop_reason == "dead_batch"
    assert verdict.spent_usd == pytest.approx(12 * 0.05 + 12 * CAP)
    assert verdict.cost_known is False


def test_a_run_that_stops_inside_its_warm_up_still_reports_cost(project: Path) -> None:
    Ledger().set_limit("anthropic", 100.0)
    toml = project / "canary.toml"
    toml.write_text(toml.read_text().replace("[stats]", "[stats]\nwarmup_batches = 1"))
    verdict = _compare(project, PaidRunner(cost=0.05), max_batches=3, max_usd=100.0).verdict
    assert verdict.batches_run == 1  # flagged in the first batch
    assert verdict.metrics_from_batch == 0
    assert any(m.metric == "reported_cost_usd" for m in verdict.metrics)


def test_multi_step_tasks_are_refused(project: Path) -> None:
    task = project / "tasks" / "task-0" / "task.toml"
    task.write_text(task.read_text() + '\n[[steps]]\nname = "one"\n\n[[steps]]\nname = "two"\n')
    with pytest.raises(ValueError, match="multi-step Harbor task"):
        load_suite(load_config(project))


def test_simulated_runs_never_touch_the_ledger(simulated_project: Path) -> None:
    result = cli.invoke(
        app,
        [
            "compare",
            "good",
            "same",
            "-c",
            str(simulated_project),
            "--max-batches",
            "1",
            "--no-report",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert Ledger().pools() == []
    for root, _dirs, files in os.walk(simulated_project):
        Path(root).chmod(0o755)
        for f in files:
            (Path(root) / f).chmod(0o644)


def test_ledger_commands() -> None:
    def run(*args: str) -> Any:
        return cli.invoke(app, ["ledger", *args], catch_exceptions=False)

    assert "no pools yet" in run("status").output
    assert "limit $22.50" in run("limit", "anthropic", "22.5").output
    assert "limit $22.50" in run("limit", "anthropic", "99", "--if-unset").output
    assert "spent $1.30" in run("correct", "anthropic", "--add", "1.3", "--note", "spike").output
    assert "spent $1.00" in run("correct", "anthropic", "--remove", "0.3", "--note", "x").output
    assert run("correct", "anthropic", "--note", "neither").exit_code == 2
    Ledger().reserve("anthropic", 4.0, run_id="run-a", batch=0)
    status = run("status").output
    assert "held $4.00" in status
    assert "run run-a  batch 0" in status
    young = run("release", "anthropic", "--run-id", "run-a", "--actual-usd", "1", "--note", "n")
    assert young.exit_code == 2
    assert "may still be running" in young.output
    forced = run(
        "release", "anthropic", "--run-id", "run-a", "--actual-usd", "1", "--note", "n", "--force"
    )
    assert "released $4.00  run run-a  batch 0" in forced.output
    assert "spent $2.00" in forced.output
    assert (
        run(
            "release", "anthropic", "--run-id", "run-a", "--actual-usd", "0", "--note", "n"
        ).exit_code
        == 2
    )


def test_a_dead_batch_exits_2_and_is_not_a_tested_release(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_canary import cli as cli_module
    from agent_canary import releases

    toml = project / "canary.toml"
    toml.write_text(toml.read_text() + '\n[watch.cc]\nbaseline = "base"\n')
    monkeypatch.setattr(
        releases,
        "https_request",
        lambda method, url, headers, body: (200, json.dumps({"latest": "1.0.5"}).encode()),
    )
    Ledger().set_limit("anthropic", 100.0)

    # Refused before anything started: the release is not marked as failed.
    monkeypatch.setattr(cli_module, "_runner", lambda loaded, env_file=None: PaidRunner())
    refused = cli.invoke(
        app, ["watch", "--run", "-c", str(project), "--max-usd", "1", "--no-report"]
    )
    assert refused.exit_code == 2
    assert "more than max_usd" in refused.output
    assert not (project / ".canary" / "watch.json").exists()

    # A dead candidate arm: exit 2, recorded as failed, not as tested.
    dead = PaidRunner(cost=None, error_pin="base-1.0.5")
    monkeypatch.setattr(cli_module, "_runner", lambda loaded, env_file=None: dead)
    result = cli.invoke(
        app, ["watch", "--run", "-c", str(project), "--max-usd", "100", "--no-report"]
    )
    assert result.exit_code == 2
    assert "stopped early: a batch produced no usable pairs" in result.output
    state = json.loads((project / ".canary" / "watch.json").read_text())["cc"]
    assert state.get("last_failed") == "1.0.5"
    assert "last_tested" not in state

    compare = cli.invoke(
        app, ["compare", "base", "cand", "-c", str(project), "--max-usd", "100", "--no-report"]
    )
    assert compare.exit_code == 1  # a healthy compare still exits by its verdict
    monkeypatch.setattr(
        cli_module, "_runner", lambda loaded, env_file=None: PaidRunner(cost=None, error_pin="cand")
    )
    dead_compare = cli.invoke(
        app, ["compare", "base", "cand", "-c", str(project), "--max-usd", "100", "--no-report"]
    )
    assert dead_compare.exit_code == 2
    assert "spent<=$" in dead_compare.output


def test_dry_run_prints_the_worst_case_and_spends_nothing(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_canary import cli as cli_module

    monkeypatch.setattr(cli_module, "_runner", lambda loaded, env_file=None: PaidRunner())
    Ledger().set_limit("anthropic", 20.0)
    result = cli.invoke(
        app,
        [
            "compare",
            "base",
            "cand",
            "-c",
            str(project),
            "--dry-run",
            "--max-batches",
            "5",
            "--max-usd",
            "8",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    out = result.output
    assert "nothing is spent" in out
    assert "24 per batch" in out
    assert "$0.290 per trial  pool anthropic" in out
    # worst run = one unchecked batch ($6.96) + max_usd x (1 - 1/5) = 6.96 + 6.4
    assert "$6.96 for one batch; $13.36 for the run" in out
    assert "each batch reserves $6.96, so 2 of 5 batches fit" in out
    assert "REFUSED" not in out
    assert not (project / ".canary" / "runs").exists()

    too_small = cli.invoke(
        app,
        ["compare", "base", "cand", "-c", str(project), "--dry-run", "--max-usd", "5"],
        catch_exceptions=False,
    )
    assert "REFUSED  one batch could cost $6.96" in too_small.output

    refused = cli.invoke(app, ["compare", "base", "uncapped", "-c", str(project), "--dry-run"])
    assert refused.exit_code == 2
    assert "no enforced per-trial spending bound" in refused.output


def test_validate_warns_about_effort_on_a_model_that_ignores_it(project: Path) -> None:
    toml = project / "canary.toml"
    toml.write_text(
        toml.read_text()
        + '\n[pins.haiku-low]\nharness = "claude-code"\nversion = "1.0.0"\n'
        + 'model = "anthropic/claude-haiku-4-5"\n'
        + 'options = { max_budget_usd = "0.08", reasoning_effort = "low" }\n'
    )
    out = cli.invoke(app, ["validate", "-c", str(project)], catch_exceptions=False).output
    assert "haiku-low: Claude Code ignores reasoning_effort" in out
    assert "cap/trial=$0.29" in out
    assert "cap/trial=NO CAP" in out  # the uncapped pin
