"""`canary` command-line interface."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

import typer

from agent_canary import __version__, alerts, logs, releases
from agent_canary.budget import BudgetError, ledger_for, pin_cap_usd
from agent_canary.bundle import BundleError, RunBundle, find_bundle, runs_dir
from agent_canary.config import LoadedConfig, load_config
from agent_canary.ledger import LedgerError, PoolStatus
from agent_canary.orchestrate import (
    PinDriftError,
    RunOutcome,
    describe_plan,
    index_path,
    run_compare,
    run_single,
)
from agent_canary.report import render_report
from agent_canary.runners import Runner, RunnerError, RunnerNotStarted
from agent_canary.runners.harbor import HarborRunner
from agent_canary.runners.simulated import SimulatedRunner
from agent_canary.stats import min_discordant_to_detect
from agent_canary.store import RunIndex
from agent_canary.suite import SuiteError, load_suite
from agent_canary.verifier import RULES_VERSION, check_trial

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Detect when a coding-agent harness or model update makes it worse or pricier.",
)
index_app = typer.Typer(no_args_is_help=True, help="Maintain the derived SQLite run index.")
app.add_typer(index_app, name="index")
ledger_app = typer.Typer(
    no_args_is_help=True,
    help="The campaign ledger: a lifetime spending limit per credit pool, across all runs.",
)
app.add_typer(ledger_app, name="ledger")

log = logging.getLogger("agent_canary.cli")

ConfigOpt = Annotated[
    Path, typer.Option("--config", "-c", help="Path to canary.toml or its directory.")
]
EnvFileOpt = Annotated[
    Path | None,
    typer.Option(help="Gitignored .env with API keys for the harness (overrides [runner])."),
]

DryRunOpt = Annotated[
    bool,
    typer.Option("--dry-run", help="Print what the run could cost and what the ledger has left."),
]

EXIT_OK, EXIT_REGRESSION, EXIT_ERROR = 0, 1, 2

# Harness options that a model silently ignores make a comparison a paid A/A run.
_NO_EFFORT_MODELS = ("haiku",)


@app.callback()
def _main(
    log_level: Annotated[str | None, typer.Option(help="DEBUG, INFO, WARNING, ...")] = None,
    log_format: Annotated[str | None, typer.Option(help="text or json")] = None,
) -> None:
    logs.configure(log_level, log_format)


def _load(config: Path) -> LoadedConfig:
    try:
        return load_config(config)
    except FileNotFoundError:
        typer.secho(f"config not found: {config}", fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None
    except ValueError as exc:  # pydantic.ValidationError subclasses ValueError
        typer.secho(f"invalid config {config}:\n{exc}", fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None


def _runner(loaded: LoadedConfig, env_file: Path | None = None) -> Runner:
    cfg = loaded.config
    if cfg.runner.kind == "simulated":
        return SimulatedRunner(
            cfg.runner.simulated, seed=cfg.stats.seed, task_spread=cfg.runner.simulated_task_spread
        )
    runner_cfg = cfg.runner
    if env_file is not None:
        runner_cfg = runner_cfg.model_copy(update={"env_file": env_file.resolve()})
    return HarborRunner(runner_cfg, cwd=loaded.root, pass_threshold=cfg.stats.pass_threshold)


def _report_path(loaded: LoadedConfig, run_id: str) -> Path:
    return loaded.home / "reports" / f"{run_id}.html"


def _send_alerts(
    loaded: LoadedConfig, bundle: RunBundle, *, dry_run: bool = False, force: bool = False
) -> bool:
    """Alert on a compare run if `[alerts]` is configured and a condition is met.

    Returns False only when a delivery was attempted and failed.
    """
    cfg = loaded.config.alerts
    verdict = bundle.verdict()
    if verdict is None:
        typer.secho("alerts apply to compare runs only", fg="yellow", err=True)
        return True
    reasons = alerts.alert_reasons(verdict, list(cfg.on))
    targets = alerts.channels(cfg)
    if not reasons and not force:
        if dry_run:
            typer.echo(f"no alert: none of {list(cfg.on)} is met")
        return True
    alert = alerts.build_alert(bundle.manifest(), verdict, reasons)
    if dry_run:
        typer.echo(f"channels: {', '.join(targets) or '(none configured)'}")
        typer.echo(f"title: {alert.title}\n\n{alert.markdown}\n\n--- slack ---\n{alert.slack_text}")
        return True
    if not targets:
        return True
    ok = True
    for d in alerts.dispatch(cfg, alert, os.environ):
        typer.secho(f"alert {d.channel}: {d.detail}", fg=None if d.ok else "yellow")
        ok = ok and d.ok
    return ok


@app.command()
def version() -> None:
    """Print the canary version."""
    typer.echo(__version__)


@app.command()
def validate(config: ConfigOpt = Path("canary.toml")) -> None:
    """Check canary.toml and the task suite; print pins and their fingerprints."""
    loaded = _load(config)
    try:
        suite = load_suite(loaded)
    except SuiteError as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None
    cfg = loaded.config
    typer.echo(f"suite    {suite.name}: {len(suite.tasks)} tasks under {suite.root}")
    if suite.git:
        typer.echo(f"commit   {suite.git.commit[:12]}{' (dirty)' if suite.git.dirty else ''}")
    for t in suite.tasks:
        typer.echo(f"  task   {t.name:<32} {t.digest[:12]}")
    for name, pin in cfg.pins.items():
        cap = pin_cap_usd(loaded, pin)
        bound = "free" if pin.pool() is None else ("NO CAP" if cap is None else f"${cap:.2f}")
        typer.echo(
            f"pin      {name:<16} {pin.harness}@{pin.version or '-'} model={pin.model or '-'} "
            f"fp={pin.fingerprint(loaded.root)[:12]} cap/trial={bound}"
        )
        model = (pin.model or "").lower()
        if "reasoning_effort" in pin.options and any(m in model for m in _NO_EFFORT_MODELS):
            typer.secho(
                f"warning  {name}: Claude Code ignores reasoning_effort on {pin.model}; an "
                "effort comparison on this model is a paid A/A run",
                fg="yellow",
            )
        if pin.pool() is not None and cap is None and cfg.runner.kind == "harbor":
            typer.secho(
                f"warning  {name}: no per-trial spending bound; a real run will be refused",
                fg="yellow",
            )
    per_batch = len(suite.tasks) * cfg.budget.attempts_per_batch
    min_pairs = min_discordant_to_detect(cfg.stats.alpha, cfg.stats.mixture_max)
    typer.echo(
        f"compare  alpha={cfg.stats.alpha} ({cfg.stats.alternative}); needs >= "
        f"{min_pairs} discordant pairs to flag; "
        f"{per_batch} pairs/batch, <= {cfg.budget.max_batches} batches, <= ${cfg.budget.max_usd:g}"
    )
    typer.echo(f"runner   {cfg.runner.kind}")


@app.command()
def run(
    pin: Annotated[str, typer.Argument(help="Pin name from canary.toml.")],
    config: ConfigOpt = Path("canary.toml"),
    attempts: Annotated[int, typer.Option(min=1, help="Attempts per task.")] = 1,
    env_file: EnvFileOpt = None,
    report: Annotated[bool, typer.Option(help="Render the HTML report.")] = True,
    max_usd: Annotated[
        float | None, typer.Option(help="Refuse if the run's worst case is above this.")
    ] = None,
    dry_run: DryRunOpt = False,
) -> None:
    """Run the suite once on a single pin and store an immutable bundle."""
    loaded = _load(config)
    try:
        suite = load_suite(loaded)
        runner = _runner(loaded, env_file)
        if dry_run:
            _print_plan(loaded, suite, runner, [pin], attempts, 1, max_usd)
            return
        outcome = run_single(loaded, suite, runner, pin, attempts=attempts, max_usd=max_usd)
    except _RUN_ERRORS as exc:
        raise _exit_for(exc) from None
    trials = outcome.bundle.trials()
    counts = {s: sum(t.status.value == s for t in trials) for s in ("pass", "fail", "error")}
    typer.echo(
        f"run {outcome.bundle.run_id}: {counts['pass']} passed, {counts['fail']} failed, "
        f"{counts['error']} errored (of {len(trials)})"
    )
    kinds = sorted(
        {t.exception_type for t in trials if t.status.value == "error" and t.exception_type}
    )
    if kinds:
        typer.secho(f"errors: {', '.join(kinds)} (see the report)", fg="yellow")
    if report:
        path = render_report(outcome.bundle, _report_path(loaded, outcome.bundle.run_id))
        typer.echo(f"report {path}")


# Errors raised before a run could spend anything: bad config, a refused budget, a batch that
# never started. They say nothing about the harness or release under test.
_REFUSALS = (
    KeyError,
    ValueError,
    SuiteError,
    BudgetError,
    LedgerError,
    RunnerNotStarted,
    BundleError,
)
_RUN_ERRORS = (*_REFUSALS, RunnerError, PinDriftError)


class _Refused(typer.Exit):
    """Exit for a run that was refused before it started."""


def _exit_for(exc: Exception) -> typer.Exit:
    typer.secho(f"error: {exc}", fg="red", err=True)
    return _Refused(EXIT_ERROR) if isinstance(exc, _REFUSALS) else typer.Exit(EXIT_ERROR)


def _print_plan(
    loaded: LoadedConfig,
    suite: object,
    runner: Runner,
    pins: list[str],
    attempts: int,
    max_batches: int,
    max_usd: float | None,
) -> None:
    typer.echo("dry run: nothing is started and nothing is spent")
    for line in describe_plan(
        loaded,
        suite,  # type: ignore[arg-type]
        runner,
        pins,
        attempts=attempts,
        max_batches=max_batches,
        max_usd=max_usd,
    ):
        typer.echo(line)


def _compare(
    loaded: LoadedConfig,
    baseline: str,
    candidate: str,
    *,
    max_usd: float | None,
    max_batches: int | None,
    env_file: Path | None,
    report: bool,
    alert: bool,
    dry_run: bool = False,
    continue_from: str | None = None,
) -> RunOutcome | None:
    """Run a compare, print its result, render the report and send alerts."""
    try:
        suite = load_suite(loaded)
        runner = _runner(loaded, env_file)
        if dry_run:
            cfg = loaded.config.budget
            _print_plan(
                loaded,
                suite,
                runner,
                [baseline, candidate],
                cfg.attempts_per_batch,
                cfg.max_batches if max_batches is None else max_batches,
                cfg.max_usd if max_usd is None else max_usd,
            )
            return None
        prior = find_bundle(loaded.home, continue_from) if continue_from else None
        outcome = run_compare(
            loaded,
            suite,
            runner,
            baseline,
            candidate,
            max_usd=max_usd,
            max_batches=max_batches,
            continue_from=prior,
        )
    except _RUN_ERRORS as exc:
        raise _exit_for(exc) from None
    v = outcome.verdict
    assert v is not None
    colour = {"regression": "red", "improvement": "green"}.get(v.decision, "yellow")
    typer.secho(
        f"{v.decision.upper()}  E={v.e_value:.3g} (threshold {1 / v.alpha:g})  p<={v.p_value:.3g}  "
        f"stop={v.stop_reason}  batches={v.batches_run}  "
        # Without a real cost for every trial the figure includes trials charged at their cap.
        f"spent{'=' if v.cost_known or not v.spent_usd else '<='}${v.spent_usd:.2f}",
        fg=colour,
    )
    typer.echo(
        f"pass rate  {v.baseline.pin}: {v.baseline.passes}/{v.baseline.n}   "
        f"{v.candidate.pin}: {v.candidate.passes}/{v.candidate.n}   "
        f"discordant {v.n_discordant} ({v.n_regress} regress / {v.n_improve} improve)"
    )
    for m in v.metrics:
        flag = "  <- increase" if m.flagged else ""
        typer.echo(f"{m.metric:<14} x{m.ratio:.3f}  CI [{m.ci_low:.3f}, {m.ci_high:.3f}]{flag}")
    if v.stop_reason in ("dead_batch", "ledger", "futility"):
        why = {
            "dead_batch": "a batch produced no usable pairs (infrastructure errors); check the "
            "account balance and credentials before running again",
            "ledger": "the campaign ledger refused the next batch",
            "futility": "the candidate was not behind by enough at the futility look",
        }[v.stop_reason]
        typer.secho(f"stopped early: {why}", fg="yellow")
    for arm in (v.baseline, v.candidate):
        if arm.cap_hits:
            typer.secho(
                f"cap hits   {arm.pin}: {arm.cap_hits} trials were stopped by a spend or turn "
                "cap and scored on what they had finished; unequal counts between arms bias "
                "the comparison",
                fg="yellow",
            )
    for arm in (v.baseline, v.candidate):
        if arm.false_success:
            typer.secho(
                f"false success  {arm.pin}: {arm.false_success} of {arm.claims} "
                '"tests pass" claims lack a passing test run after the last edit',
                fg="yellow",
            )
    typer.echo(f"run {outcome.bundle.run_id}")
    if report:
        path = render_report(outcome.bundle, _report_path(loaded, outcome.bundle.run_id))
        typer.echo(f"report {path}")
    if alert:
        _send_alerts(loaded, outcome.bundle)  # a failed delivery never changes the exit code
    return outcome


def _verdict_exit(outcome: RunOutcome) -> int:
    """1 for a regression, 2 for a run that produced no evidence, otherwise 0."""
    assert outcome.verdict is not None
    if outcome.verdict.decision == "regression":
        return EXIT_REGRESSION
    return EXIT_ERROR if outcome.verdict.stop_reason == "dead_batch" else EXIT_OK


@app.command()
def compare(
    baseline: Annotated[str, typer.Argument(help="Baseline pin name.")],
    candidate: Annotated[str, typer.Argument(help="Candidate pin name.")],
    config: ConfigOpt = Path("canary.toml"),
    max_usd: Annotated[float | None, typer.Option(help="Override [budget] max_usd.")] = None,
    max_batches: Annotated[int | None, typer.Option(help="Override [budget] max_batches.")] = None,
    env_file: EnvFileOpt = None,
    report: Annotated[bool, typer.Option(help="Render the HTML report.")] = True,
    alert: Annotated[bool, typer.Option(help="Send alerts configured in [alerts].")] = True,
    dry_run: DryRunOpt = False,
    continue_from: Annotated[
        str | None,
        typer.Option(
            "--continue-from",
            help="Extend an earlier compare (run id) with more batches; max-batches and "
            "max-usd then count the new batches only.",
        ),
    ] = None,
) -> None:
    """Sequential paired A/B test of two pins. Exit code 1 means a regression was detected."""
    outcome = _compare(
        _load(config),
        baseline,
        candidate,
        max_usd=max_usd,
        max_batches=max_batches,
        env_file=env_file,
        report=report,
        alert=alert,
        dry_run=dry_run,
        continue_from=continue_from,
    )
    if outcome is None:
        return
    raise typer.Exit(_verdict_exit(outcome))


@app.command()
def watch(
    config: ConfigOpt = Path("canary.toml"),
    run: Annotated[
        bool, typer.Option("--run", help="Compare each new release against its baseline pin.")
    ] = False,
    retest: Annotated[bool, typer.Option(help="Test a release even if already tested.")] = False,
    max_usd: Annotated[float | None, typer.Option(help="Override [budget] max_usd.")] = None,
    max_batches: Annotated[int | None, typer.Option(help="Override [budget] max_batches.")] = None,
    env_file: EnvFileOpt = None,
    report: Annotated[bool, typer.Option(help="Render the HTML report.")] = True,
    alert: Annotated[bool, typer.Option(help="Send alerts configured in [alerts].")] = True,
    dry_run: DryRunOpt = False,
) -> None:
    """Check each watch entry for a new harness release; with --run, test it.

    The candidate is the baseline pin with only the version changed. Exit code 1 means a tested
    release regressed. Without --run nothing is spent.
    """
    loaded = _load(config)
    if not loaded.config.watch:
        typer.secho("no [watch.<name>] entries in the config", fg="yellow", err=True)
        raise typer.Exit(EXIT_ERROR)
    regressed = failed = False
    for name, entry in loaded.config.watch.items():
        try:
            cand = releases.check_watch(name, entry, loaded)
        except (KeyError, releases.ReleaseError) as exc:
            typer.secho(f"watch {name}: {exc}", fg="red", err=True)
            failed = True
            continue
        line = (
            f"watch {name}: {cand.pin.harness} {entry.channel} is {cand.latest}, "
            f"baseline {cand.baseline} is {cand.baseline_version}"
        )
        if not cand.is_new:
            typer.echo(f"{line}: nothing new")
            continue
        if cand.already_tested and not retest:
            typer.echo(f"{line}: new release already tested")
            continue
        if cand.failed_before and not retest:
            # A scheduled job must not pay again on every tick for a release that cannot run.
            typer.secho(
                f"{line}: an earlier attempt to test this release failed; pass --retest",
                fg="yellow",
            )
            failed = True
            continue
        if not run and not dry_run:
            typer.secho(f"{line}: NEW RELEASE, not tested (pass --run)", fg="yellow")
            continue
        typer.secho(f"{line}: NEW RELEASE, comparing", fg="yellow")
        try:
            outcome = _compare(
                loaded.with_pin(cand.pin_name, cand.pin),
                cand.baseline,
                cand.pin_name,
                max_usd=max_usd,
                max_batches=max_batches,
                env_file=env_file,
                report=report,
                alert=alert,
                dry_run=dry_run,
            )
        except _Refused:
            # Nothing was attempted, so the release is not marked: fix the cause and re-run.
            failed = True
            continue
        except typer.Exit:
            releases.record_failed(loaded.home, name, cand.latest)
            failed = True
            continue
        if outcome is None:
            continue
        assert outcome.verdict is not None
        if outcome.verdict.stop_reason == "dead_batch":
            # No evidence either way. Do not call the release tested, and do not pay for the
            # same dead batch on every scheduled tick.
            releases.record_failed(loaded.home, name, cand.latest)
            failed = True
            continue
        releases.record_tested(
            loaded.home, name, cand.latest, outcome.bundle.run_id, outcome.verdict.decision
        )
        regressed = regressed or outcome.verdict.decision == "regression"
    if failed:
        raise typer.Exit(EXIT_ERROR)
    raise typer.Exit(EXIT_REGRESSION if regressed else EXIT_OK)


@app.command("alert")
def alert_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id or unique prefix.")],
    config: ConfigOpt = Path("canary.toml"),
    dry_run: Annotated[bool, typer.Option(help="Print the alert; send nothing.")] = False,
    force: Annotated[bool, typer.Option(help="Send even if no [alerts] condition is met.")] = False,
) -> None:
    """Send (or preview) the alert for a stored compare run."""
    loaded = _load(config)
    try:
        bundle = find_bundle(loaded.home, run_id)
    except BundleError as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None
    if not _send_alerts(loaded, bundle, dry_run=dry_run, force=force):
        raise typer.Exit(EXIT_ERROR)


@app.command("report")
def report_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id or unique prefix.")],
    config: ConfigOpt = Path("canary.toml"),
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
) -> None:
    """Render (or re-render) the HTML report for a run."""
    loaded = _load(config)
    try:
        bundle = find_bundle(loaded.home, run_id)
    except BundleError as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None
    typer.echo(render_report(bundle, output or _report_path(loaded, bundle.run_id)))


@app.command()
def verify(
    run_id: Annotated[str, typer.Argument(help="Run id or unique prefix.")],
    config: ConfigOpt = Path("canary.toml"),
) -> None:
    """Recompute a bundle's checksums."""
    loaded = _load(config)
    try:
        bundle = find_bundle(loaded.home, run_id)
    except BundleError as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None
    problems = bundle.verify()
    if problems:
        for p in problems:
            typer.secho(p, fg="red")
        raise typer.Exit(EXIT_ERROR)
    typer.echo(f"{bundle.run_id}: intact")


@app.command()
def claims(
    run_id: Annotated[str, typer.Argument(help="Run id or unique prefix.")],
    config: ConfigOpt = Path("canary.toml"),
) -> None:
    """Re-check "tests pass" claims in a run's transcripts with the current verifier rules."""
    loaded = _load(config)
    try:
        bundle = find_bundle(loaded.home, run_id)
    except BundleError as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None
    checked = [
        (t, check)
        for t in bundle.trials()
        if t.trial_dir and t.status.value != "error"
        for check in [check_trial(bundle.path / t.trial_dir)]
        if check is not None
    ]
    typer.echo(f"{bundle.run_id}: {len(checked)} transcripts checked (rules v{RULES_VERSION})")
    for pin in sorted({t.pin for t, _ in checked}):
        mine = [(t, c) for t, c in checked if t.pin == pin]
        n = {v: sum(c.verdict == v for _, c in mine) for v in ("supported", "false_success")}
        claimed = [(t, c) for t, c in mine if c.verdict != "no_claim"]
        hidden_fail = sum(t.status.value == "fail" for t, _ in claimed)
        typer.echo(
            f"{pin:<16} claims {len(claimed)}/{len(mine)}  supported {n['supported']}  "
            f"false success {n['false_success']}  "
            f"unverifiable {len(claimed) - n['supported'] - n['false_success']}  "
            f"claimed but failed hidden tests {hidden_fail}"
        )
    for t, c in checked:
        if c.verdict in ("false_success", "unverifiable"):
            typer.secho(
                f"  {c.verdict:<13} {t.trial_name} ({t.pin}, {t.status.value}): {c.reason}; "
                f"step {c.claim_step}: {c.claim_excerpt!r}",
                fg="yellow",
            )


@app.command()
def runs(
    config: ConfigOpt = Path("canary.toml"),
    limit: Annotated[int, typer.Option(min=1)] = 20,
) -> None:
    """List recent runs from the index."""
    loaded = _load(config)
    rows = RunIndex(index_path(loaded.home)).list_runs(limit)
    if not rows:
        typer.echo("no runs yet")
        return
    for r in rows:
        arms = f"{r['baseline']} -> {r['candidate']}" if r["kind"] == "compare" else ""
        verdict = f"{r['decision']} ({r['stop_reason']})" if r["decision"] else ""
        typer.echo(f"{r['run_id']:<40} {r['kind']:<8} {arms:<32} {verdict}")


def _echo_pool(status: PoolStatus) -> None:
    if status.limit_usd is None:
        typer.echo(f"{status.pool:<12} no limit set; ${status.committed_usd:.2f} committed")
        return
    typer.echo(
        f"{status.pool:<12} limit ${status.limit_usd:.2f}   spent ${status.settled_usd:.2f}   "
        f"held ${status.reserved_usd:.2f}   left ${status.remaining_usd:.2f}"
    )


def _ledger_call(action: object) -> None:
    try:
        action()  # type: ignore[operator]
    except LedgerError as exc:
        typer.secho(f"error: {exc}", fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None


# A reservation younger than this may belong to a batch that is still running.
_RELEASE_MIN_AGE_SEC = 4 * 3600.0


@ledger_app.command("status")
def ledger_status() -> None:
    """Show each pool's limit, settled spend, held reservations and what is left."""
    ledger = ledger_for()
    typer.echo(f"ledger   {ledger.directory}")

    def show() -> None:
        pools = ledger.pools()
        if not pools:
            typer.echo("no pools yet; set a limit with `canary ledger limit <pool> <usd>`")
        for pool in pools:
            _echo_pool(ledger.status(pool))
            for e in ledger.open_reservations(pool):
                typer.echo(
                    f"  held ${e['usd']:.2f}  run {e.get('run_id')}  batch {e.get('batch')}  "
                    f"since {e.get('ts')}"
                )

    _ledger_call(show)


@ledger_app.command("limit")
def ledger_limit(
    pool: Annotated[str, typer.Argument(help="Credit pool, e.g. anthropic or openai.")],
    usd: Annotated[float, typer.Argument(min=0, help="Lifetime limit in dollars.")],
    if_unset: Annotated[
        bool,
        typer.Option("--if-unset", help="Do nothing if the pool already has a limit (for CI)."),
    ] = False,
) -> None:
    """Set the lifetime spending limit for a pool. Paid runs are refused without one."""
    _ledger_call(lambda: _echo_pool(ledger_for().set_limit(pool, usd, if_unset=if_unset)))


@ledger_app.command("correct")
def ledger_correct(
    pool: Annotated[str, typer.Argument(help="Credit pool.")],
    note: Annotated[str, typer.Option(help="Why, e.g. the console figure and date.")],
    add: Annotated[float | None, typer.Option(min=0, help="Dollars the ledger missed.")] = None,
    remove: Annotated[
        float | None, typer.Option(min=0, help="Dollars the ledger over-counted.")
    ] = None,
) -> None:
    """Adjust a pool so it matches the provider's console after reconciling by hand."""
    if (add is None) == (remove is None):
        typer.secho("error: give exactly one of --add or --remove", fg="red", err=True)
        raise typer.Exit(EXIT_ERROR)
    usd = add if add is not None else -(remove or 0.0)
    _ledger_call(lambda: _echo_pool(ledger_for().correct(pool, usd, note)))


@ledger_app.command("release")
def ledger_release(
    pool: Annotated[str, typer.Argument(help="Credit pool.")],
    run_id: Annotated[str, typer.Option("--run-id", help="The run whose reservations to settle.")],
    actual_usd: Annotated[
        float, typer.Option("--actual-usd", min=0, help="What the console shows that run cost.")
    ],
    note: Annotated[str, typer.Option(help="Why, e.g. the console figure and date.")],
    force: Annotated[
        bool, typer.Option("--force", help="Release even if the reservation is recent.")
    ] = False,
) -> None:
    """Settle the reservations a crashed or interrupted run left open.

    Only for a run that has certainly stopped: check that no `harbor` process or container of
    that run is still alive first, because a running batch keeps spending.
    """

    def release() -> None:
        ledger = ledger_for()
        released = ledger.release(
            pool, run_id, actual_usd, note, min_age_sec=0.0 if force else _RELEASE_MIN_AGE_SEC
        )
        for e in released:
            typer.echo(f"released ${e['usd']:.2f}  run {e.get('run_id')}  batch {e.get('batch')}")
        _echo_pool(ledger.status(pool))

    _ledger_call(release)


@index_app.command("rebuild")
def index_rebuild(config: ConfigOpt = Path("canary.toml")) -> None:
    """Rebuild the SQLite index from the run bundles on disk."""
    loaded = _load(config)
    n = RunIndex(index_path(loaded.home)).rebuild(runs_dir(loaded.home))
    typer.echo(f"indexed {n} runs")
