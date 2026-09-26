"""`canary` command-line interface."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from agent_canary import __version__, logs
from agent_canary.bundle import BundleError, find_bundle, runs_dir
from agent_canary.config import LoadedConfig, load_config
from agent_canary.orchestrate import PinDriftError, index_path, run_compare, run_single
from agent_canary.report import render_report
from agent_canary.runners import Runner, RunnerError
from agent_canary.runners.harbor import HarborRunner
from agent_canary.runners.simulated import SimulatedRunner
from agent_canary.stats import min_discordant_to_detect
from agent_canary.store import RunIndex
from agent_canary.suite import SuiteError, load_suite

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Detect when a coding-agent harness or model update makes it worse or pricier.",
)
index_app = typer.Typer(no_args_is_help=True, help="Maintain the derived SQLite run index.")
app.add_typer(index_app, name="index")

log = logging.getLogger("agent_canary.cli")

ConfigOpt = Annotated[
    Path, typer.Option("--config", "-c", help="Path to canary.toml or its directory.")
]
EnvFileOpt = Annotated[
    Path | None,
    typer.Option(help="Gitignored .env with API keys for the harness (overrides [runner])."),
]

EXIT_OK, EXIT_REGRESSION, EXIT_ERROR = 0, 1, 2


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
        typer.echo(
            f"pin      {name:<16} {pin.harness}@{pin.version or '-'} model={pin.model or '-'} "
            f"fp={pin.fingerprint(loaded.root)[:12]}"
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
) -> None:
    """Run the suite once on a single pin and store an immutable bundle."""
    loaded = _load(config)
    try:
        outcome = run_single(
            loaded, load_suite(loaded), _runner(loaded, env_file), pin, attempts=attempts
        )
    except (KeyError, SuiteError, RunnerError, PinDriftError) as exc:
        typer.secho(f"error: {exc}", fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None
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


@app.command()
def compare(
    baseline: Annotated[str, typer.Argument(help="Baseline pin name.")],
    candidate: Annotated[str, typer.Argument(help="Candidate pin name.")],
    config: ConfigOpt = Path("canary.toml"),
    max_usd: Annotated[float | None, typer.Option(help="Override [budget] max_usd.")] = None,
    max_batches: Annotated[int | None, typer.Option(help="Override [budget] max_batches.")] = None,
    env_file: EnvFileOpt = None,
    report: Annotated[bool, typer.Option(help="Render the HTML report.")] = True,
) -> None:
    """Sequential paired A/B test of two pins. Exit code 1 means a regression was detected."""
    loaded = _load(config)
    try:
        outcome = run_compare(
            loaded,
            load_suite(loaded),
            _runner(loaded, env_file),
            baseline,
            candidate,
            max_usd=max_usd,
            max_batches=max_batches,
        )
    except (KeyError, ValueError, SuiteError, RunnerError, PinDriftError) as exc:
        typer.secho(f"error: {exc}", fg="red", err=True)
        raise typer.Exit(EXIT_ERROR) from None
    v = outcome.verdict
    assert v is not None
    colour = {"regression": "red", "improvement": "green"}.get(v.decision, "yellow")
    typer.secho(
        f"{v.decision.upper()}  E={v.e_value:.3g} (threshold {1 / v.alpha:g})  p<={v.p_value:.3g}  "
        f"stop={v.stop_reason}  batches={v.batches_run}  spent=${v.spent_usd:.2f}",
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
    typer.echo(f"run {outcome.bundle.run_id}")
    if report:
        path = render_report(outcome.bundle, _report_path(loaded, outcome.bundle.run_id))
        typer.echo(f"report {path}")
    raise typer.Exit(EXIT_REGRESSION if v.decision == "regression" else EXIT_OK)


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


@index_app.command("rebuild")
def index_rebuild(config: ConfigOpt = Path("canary.toml")) -> None:
    """Rebuild the SQLite index from the run bundles on disk."""
    loaded = _load(config)
    n = RunIndex(index_path(loaded.home)).rebuild(runs_dir(loaded.home))
    typer.echo(f"indexed {n} runs")
