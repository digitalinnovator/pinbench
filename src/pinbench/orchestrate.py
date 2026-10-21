"""The compare loop: run paired batches, update the e-process, stop on significance or budget."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pinbench import __version__
from pinbench.budget import (
    BatchCharge,
    BatchPlan,
    BudgetError,
    dead_batch,
    ledger_for,
    plan_batch,
    preflight,
)
from pinbench.bundle import RunBundle, new_run_id, runs_dir
from pinbench.config import LoadedConfig, PinSpec
from pinbench.ledger import LedgerError
from pinbench.models import (
    ArmSummary,
    BatchPoint,
    PinRecord,
    RatioEstimate,
    RunManifest,
    TaskRecord,
    TaskSummary,
    TrialRecord,
    TrialStatus,
    Verdict,
)
from pinbench.pricing import load_price_table
from pinbench.runners import BatchRequest, Runner, RunnerError, RunnerNotStarted
from pinbench.stats import (
    METRICS,
    SequentialState,
    build_pairs,
    cluster_bootstrap_ratio,
    cost_metric,
    metric_by_task,
)
from pinbench.store import RunIndex
from pinbench.suite import Suite

log = logging.getLogger(__name__)


class PinDriftError(RuntimeError):
    """The harness version that actually ran differs from the pinned version."""


@dataclass(frozen=True)
class RunOutcome:
    bundle: RunBundle
    verdict: Verdict | None


def index_path(home: Path) -> Path:
    return home / "index.db"


def _manifest(
    loaded: LoadedConfig,
    suite: Suite,
    runner: Runner,
    pins: dict[str, PinSpec],
    *,
    kind: str,
    baseline: str | None = None,
    candidate: str | None = None,
    continues: str | None = None,
) -> RunManifest:
    cfg = loaded.config
    return RunManifest(
        run_id=new_run_id(kind),
        kind="compare" if kind == "compare" else "run",
        created_at=datetime.now(UTC),
        pinbench_version=__version__,
        runner=runner.describe(),
        suite_name=suite.name,
        suite_commit=suite.git.commit if suite.git else None,
        suite_dirty=suite.git.dirty if suite.git else None,
        tasks=[TaskRecord(name=t.name, digest=t.digest) for t in suite.tasks],
        pins=[
            PinRecord(
                name=name,
                fingerprint=pin.fingerprint(loaded.root),
                spec=pin.model_dump(mode="json"),
            )
            for name, pin in pins.items()
        ],
        baseline=baseline,
        candidate=candidate,
        continues=continues,
        settings={
            "stats": cfg.stats.model_dump(mode="json"),
            "budget": cfg.budget.model_dump(mode="json"),
            "pricing": load_price_table().describe(),
        },
    )


def _check_drift(records: list[TrialRecord], pins: dict[str, PinSpec]) -> None:
    drifted = sorted(
        {
            (r.pin, pins[r.pin].version, r.installed_version)
            for r in records
            if pins[r.pin].version
            and r.version_source == "trajectory"
            and r.installed_version != pins[r.pin].version
        },
        key=str,
    )
    if drifted:
        detail = "; ".join(f"{pin}: pinned {want}, ran {got}" for pin, want, got in drifted)
        raise PinDriftError(f"harness version drift: {detail}")


def _arm(records: list[TrialRecord], pin: str) -> ArmSummary:
    mine = [r for r in records if r.pin == pin]
    # Infrastructure errors never reached the agent's final report, so they are not checked.
    checks = [r.claim_check for r in mine if r.claim_check and r.status is not TrialStatus.ERROR]
    return ArmSummary(
        pin=pin,
        n=sum(r.status is not TrialStatus.ERROR for r in mine),
        passes=sum(r.status is TrialStatus.PASS for r in mine),
        errors=sum(r.status is TrialStatus.ERROR for r in mine),
        checked=len(checks),
        claims=sum(c.verdict != "no_claim" for c in checks),
        false_success=sum(c.verdict == "false_success" for c in checks),
        cap_hits=sum((r.harness_stop or "").startswith("error_max_") for r in mine),
    )


def _per_task(
    records: list[TrialRecord], baseline: str, candidate: str, task_names: list[str]
) -> list[TaskSummary]:
    pairs, _ = build_pairs(records, baseline, candidate)
    regress: dict[str, int] = defaultdict(int)
    improve: dict[str, int] = defaultdict(int)
    for p in pairs:
        regress[p.task] += p.regress
        improve[p.task] += p.improve
    out = []
    for task in task_names:
        b = [
            r
            for r in records
            if r.task == task and r.pin == baseline and r.status is not TrialStatus.ERROR
        ]
        c = [
            r
            for r in records
            if r.task == task and r.pin == candidate and r.status is not TrialStatus.ERROR
        ]
        out.append(
            TaskSummary(
                task=task,
                baseline_passes=sum(r.status is TrialStatus.PASS for r in b),
                baseline_n=len(b),
                candidate_passes=sum(r.status is TrialStatus.PASS for r in c),
                candidate_n=len(c),
                n_regress=regress[task],
                n_improve=improve[task],
            )
        )
    return out


def _metrics_from(records: list[TrialRecord], loaded: LoadedConfig) -> int:
    """First batch used for cost metrics: the warm-up setting, unless the run stopped inside it.

    A run that ends within its warm-up batches would otherwise report no cost comparison at
    all, so it falls back to every batch and the verdict records that it did.
    """
    warmup = loaded.config.stats.warmup_batches
    return warmup if any(r.batch >= warmup for r in records) else 0


def _metrics(
    records: list[TrialRecord], baseline: str, candidate: str, loaded: LoadedConfig
) -> list[RatioEstimate]:
    stats = loaded.config.stats
    records = [r for r in records if r.batch >= _metrics_from(records, loaded)]
    out = []
    metrics = dict(
        [cost_metric(r for r in records if r.pin in (baseline, candidate)), *METRICS.items()]
    )
    for i, (metric, attr) in enumerate(metrics.items()):
        est = cluster_bootstrap_ratio(
            metric,
            metric_by_task(records, baseline, attr),
            metric_by_task(records, candidate, attr),
            n_resamples=stats.bootstrap_resamples,
            confidence=stats.confidence,
            seed=stats.seed + i,
            threshold=stats.cost_threshold,
        )
        if est is not None:
            out.append(est)
    return out


_CONTINUABLE = frozenset({"max_batches", "budget_usd", "ledger"})


def _prior_run(
    prior: RunBundle | None,
    loaded: LoadedConfig,
    suite: Suite,
    pins: dict[str, PinSpec],
    baseline: str,
    candidate: str,
) -> tuple[SequentialState, list[BatchPoint], list[TrialRecord], float, bool]:
    """The state to start from: empty, or an earlier compare replayed batch by batch."""
    cfg = loaded.config
    if prior is None:
        return SequentialState(q_max=cfg.stats.mixture_max), [], [], 0.0, True
    manifest, verdict = prior.manifest(), prior.verdict()
    problems = []
    if manifest.kind != "compare" or verdict is None:
        problems.append("it is not a finished compare run")
    if (manifest.baseline, manifest.candidate) != (baseline, candidate):
        problems.append(f"it compared {manifest.baseline} with {manifest.candidate}")
    then = {p.name: p.fingerprint for p in manifest.pins}
    for name, pin in pins.items():
        if then.get(name) != pin.fingerprint(loaded.root):
            problems.append(f"pin {name!r} has changed since")
    if [(t.name, t.digest) for t in manifest.tasks] != [(t.name, t.digest) for t in suite.tasks]:
        problems.append("its tasks are not the suite's tasks now")
    keys = ("alpha", "alternative", "mixture_max", "pass_threshold")
    stats_then = manifest.settings.get("stats", {})
    if any(stats_then.get(k) != getattr(cfg.stats, k) for k in keys):
        problems.append("its test settings differ")
    if verdict is not None and verdict.stop_reason not in _CONTINUABLE:
        problems.append(f"it stopped for {verdict.stop_reason!r}, which is final")
    if problems:
        raise ValueError(f"cannot continue run {prior.run_id}: " + "; ".join(problems))
    assert verdict is not None
    records = prior.trials()
    state = SequentialState(q_max=cfg.stats.mixture_max)
    for batch in sorted({r.batch for r in records}):
        pairs, _ = build_pairs([r for r in records if r.batch == batch], baseline, candidate)
        state = state.update(pairs, cfg.stats.alternative)
    if (state.n_regress, state.n_improve) != (verdict.n_regress, verdict.n_improve):
        raise ValueError(
            f"cannot continue run {prior.run_id}: its trials do not reproduce its verdict"
        )
    return state, list(verdict.history), records, verdict.spent_usd, verdict.cost_known


def _validate(runner: Runner, pins: dict[str, PinSpec]) -> None:
    check = getattr(runner, "validate", None)
    if callable(check):
        check(pins)


def _run_reserved(runner: Runner, charge: BatchCharge, request: BatchRequest) -> list[TrialRecord]:
    """Run one batch under its ledger reservation and settle it.

    A batch that never started cannot have spent, so its reservation is released. Any other
    failure, including an interrupt, leaves the reservation open at the worst case on purpose:
    trials may have run, and the ledger must not under-count them.
    """
    try:
        records = runner.run_batch(request)
    except RunnerNotStarted:
        charge.cancel()
        raise
    charge.settle(records)
    return records


def run_compare(
    loaded: LoadedConfig,
    suite: Suite,
    runner: Runner,
    baseline: str,
    candidate: str,
    *,
    max_usd: float | None = None,
    max_batches: int | None = None,
    continue_from: RunBundle | None = None,
) -> RunOutcome:
    """Run a sequential paired comparison, or extend an earlier one with more batches.

    Continuing is valid for the e-process: it is a test supermartingale, so deciding to collect
    more batches after looking at the result does not raise the false-alarm rate (ADR-0003). The
    continuation must use the same pins, tasks and test settings; `max_batches` and `max_usd`
    then apply to the new batches only.
    """
    cfg = loaded.config
    if baseline == candidate:
        raise ValueError("baseline and candidate must be different pins")
    pins = {baseline: loaded.pin(baseline), candidate: loaded.pin(candidate)}
    prior = _prior_run(continue_from, loaded, suite, pins, baseline, candidate)
    budget_usd = cfg.budget.max_usd if max_usd is None else max_usd
    batch_limit = cfg.budget.max_batches if max_batches is None else max_batches
    alternative, alpha = cfg.stats.alternative, cfg.stats.alpha

    # Refuse before creating anything if the run could never start or the first batch cannot
    # be paid for (ADR-0009).
    _validate(runner, pins)
    plan = plan_batch(loaded, runner, pins, len(suite.tasks), cfg.budget.attempts_per_batch)
    ledger = ledger_for(loaded)
    preflight(plan, ledger, max_usd=budget_usd)

    manifest = _manifest(
        loaded,
        suite,
        runner,
        pins,
        kind="compare",
        baseline=baseline,
        candidate=candidate,
        continues=continue_from.run_id if continue_from else None,
    )
    bundle = RunBundle.create(runs_dir(loaded.home), manifest)
    log.info(
        "compare started",
        extra={
            "run_id": bundle.run_id,
            "baseline": baseline,
            "candidate": candidate,
            "batch_worst_case_usd": round(plan.worst_case_usd, 4),
        },
    )

    records: list[TrialRecord] = []
    state, history, prior_records, prior_spent, prior_known = prior
    first = len(history)
    stop_reason: str | None = None
    try:
        for done, batch in enumerate(range(first, first + batch_limit)):
            # Soft stop, from measured spend. A trial with no cost counts at its cap, so an
            # unknown cost can stop the run early but can never switch the check off.
            spent, _ = plan.spent(records)
            if done > 0 and spent + spent / done > budget_usd:
                stop_reason = "budget_usd"
                break
            # Hard stop: the batch's worst case must fit the pool's lifetime limit.
            try:
                charge = BatchCharge.reserve(ledger, plan, run_id=bundle.run_id, batch=batch)
            except LedgerError as exc:
                if batch == 0:
                    raise
                log.warning("ledger refused the next batch", extra={"reason": str(exc)})
                stop_reason = "ledger"
                break
            new = _run_reserved(
                runner,
                charge,
                BatchRequest(
                    batch=batch,
                    tasks=suite.tasks,
                    pins=pins,
                    attempts=cfg.budget.attempts_per_batch,
                    bundle_dir=bundle.path,
                ),
            )
            bundle.append_trials(new)
            records.extend(new)
            _check_drift(new, pins)

            batch_pairs, _ = build_pairs(new, baseline, candidate)
            state = state.update(batch_pairs, alternative)
            spent, _ = plan.spent(records)
            point = BatchPoint(
                batch=batch,
                n_pairs=state.n_pairs,
                n_discordant=state.n_discordant,
                n_regress=state.n_regress,
                n_improve=state.n_improve,
                e_value=state.e(alternative),
                spent_usd=round(prior_spent + spent, 6),
            )
            history.append(point)
            log.info("batch evaluated", extra=point.model_dump())
            if state.decision(alternative, alpha) != "inconclusive":
                stop_reason = "significant"
                break
            dead = dead_batch(new, [baseline, candidate])
            if dead is None and not batch_pairs:
                dead = "no task had a usable result in both arms"
            if dead is not None:
                # An empty account or a broken arm: more batches would cost money for nothing.
                log.error("stopping: the batch carries no evidence", extra={"reason": dead})
                stop_reason = "dead_batch"
                break
            if (
                cfg.stats.futility_after_batches == len(history)
                and state.n_regress - state.n_improve < cfg.stats.futility_min_net_regressions
            ):
                stop_reason = "futility"
                break
        else:
            stop_reason = "max_batches"
    except Exception:
        log.exception("compare aborted; sealing partial bundle", extra={"run_id": bundle.run_id})
        bundle.seal()
        RunIndex(index_path(loaded.home)).ingest(bundle)
        raise

    new_records = records
    records = prior_records + new_records
    _, dropped = build_pairs(records, baseline, candidate)
    spent, cost_known = plan.spent(new_records)
    spent, cost_known = prior_spent + spent, prior_known and cost_known
    verdict = Verdict(
        decision=state.decision(alternative, alpha),
        stop_reason=stop_reason,  # type: ignore[arg-type]
        alternative=alternative,
        alpha=alpha,
        e_value=state.e(alternative),
        p_value=state.p_value(),
        batches_run=len(history),
        spent_usd=round(spent, 6),
        cost_known=cost_known,
        n_pairs=state.n_pairs,
        n_discordant=state.n_discordant,
        n_regress=state.n_regress,
        n_improve=state.n_improve,
        dropped_pairs=dropped,
        baseline=_arm(records, baseline),
        candidate=_arm(records, candidate),
        metrics=_metrics(records, baseline, candidate, loaded),
        metrics_from_batch=_metrics_from(records, loaded),
        per_task=_per_task(records, baseline, candidate, suite.task_names),
        history=history,
    )
    bundle.write_verdict(verdict)
    bundle.seal()
    RunIndex(index_path(loaded.home)).ingest(bundle)
    log.info(
        "compare finished",
        extra={
            "run_id": bundle.run_id,
            "decision": verdict.decision,
            "stop_reason": verdict.stop_reason,
        },
    )
    return RunOutcome(bundle=bundle, verdict=verdict)


def run_single(
    loaded: LoadedConfig,
    suite: Suite,
    runner: Runner,
    pin: str,
    *,
    attempts: int,
    max_usd: float | None = None,
) -> RunOutcome:
    pins = {pin: loaded.pin(pin)}
    _validate(runner, pins)
    plan = plan_batch(loaded, runner, pins, len(suite.tasks), attempts)
    ledger = ledger_for(loaded)
    preflight(plan, ledger, max_usd=max_usd)
    bundle = RunBundle.create(
        runs_dir(loaded.home), _manifest(loaded, suite, runner, pins, kind="run")
    )
    try:
        charge = BatchCharge.reserve(ledger, plan, run_id=bundle.run_id, batch=0)
        records = _run_reserved(
            runner,
            charge,
            BatchRequest(
                batch=0, tasks=suite.tasks, pins=pins, attempts=attempts, bundle_dir=bundle.path
            ),
        )
        bundle.append_trials(records)
        _check_drift(records, pins)
    finally:
        bundle.seal()
    RunIndex(index_path(loaded.home)).ingest(bundle)
    return RunOutcome(bundle=bundle, verdict=None)


def describe_plan(
    loaded: LoadedConfig,
    suite: Suite,
    runner: Runner,
    pin_names: list[str],
    *,
    attempts: int,
    max_batches: int,
    max_usd: float | None,
) -> list[str]:
    """Lines for `--dry-run`: what one batch and the whole run could cost, and what is left."""
    pins = {name: loaded.pin(name) for name in pin_names}
    plan: BatchPlan = plan_batch(loaded, runner, pins, len(suite.tasks), attempts)
    ledger = ledger_for(loaded)
    lines = [
        f"trials   {plan.trials} per batch ({len(suite.tasks)} tasks x {attempts} attempts x "
        f"{len(pins)} pins), at most {max_batches} batches",
    ]
    for name in pin_names:
        pool = plan.pools[name] or "free"
        lines.append(f"cap      {name:<20} ${plan.caps[name]:.3f} per trial  pool {pool}")
    worst_batch = plan.worst_case_usd
    # Batch 0 runs unchecked by max_usd; afterwards the soft stop allows about one batch over.
    if max_usd is None or max_batches == 1:
        worst_run = worst_batch * max_batches
    else:
        worst_run = min(worst_batch * max_batches, worst_batch + max_usd * (1 - 1 / max_batches))
    lines.append(
        f"worst    ${worst_batch:.2f} for one batch; ${worst_run:.2f} for the run "
        "(every trial at its cap)"
    )
    if not plan.paid:
        lines.append("ledger   not used: this runner spends nothing")
    try:
        _validate(runner, pins)
        preflight(plan, ledger, max_usd=max_usd)
    except (BudgetError, RunnerError) as exc:
        lines.append(f"REFUSED  {exc}")
    for pool, usd in plan.reservations().items():
        status = ledger.status(pool)
        if status.limit_usd is None:
            lines.append(f"ledger   {pool}: NO LIMIT SET, a paid run will be refused")
            continue
        left = status.limit_usd - status.committed_usd
        fits = int(left // usd) if usd > 0 else max_batches
        lines.append(
            f"ledger   {pool}: ${status.committed_usd:.2f} of ${status.limit_usd:.2f} committed, "
            f"${left:.2f} left; each batch reserves ${usd:.2f}, so {min(fits, max_batches)} of "
            f"{max_batches} batches fit if every trial hits its cap"
        )
    return lines
