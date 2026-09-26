"""The compare loop: run paired batches, update the e-process, stop on significance or budget."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_canary import __version__
from agent_canary.bundle import RunBundle, new_run_id, runs_dir
from agent_canary.config import LoadedConfig, PinSpec
from agent_canary.models import (
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
from agent_canary.runners import BatchRequest, Runner
from agent_canary.stats import (
    METRICS,
    SequentialState,
    build_pairs,
    cluster_bootstrap_ratio,
    metric_by_task,
)
from agent_canary.store import RunIndex
from agent_canary.suite import Suite

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
) -> RunManifest:
    cfg = loaded.config
    return RunManifest(
        run_id=new_run_id(kind),
        kind="compare" if kind == "compare" else "run",
        created_at=datetime.now(UTC),
        canary_version=__version__,
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
        settings={
            "stats": cfg.stats.model_dump(mode="json"),
            "budget": cfg.budget.model_dump(mode="json"),
        },
    )


def _check_drift(records: list[TrialRecord], pins: dict[str, PinSpec]) -> None:
    drifted = sorted(
        {
            (r.pin, pins[r.pin].version, r.installed_version)
            for r in records
            if pins[r.pin].version
            and r.installed_version
            and r.installed_version != pins[r.pin].version
        },
        key=str,
    )
    if drifted:
        detail = "; ".join(f"{pin}: pinned {want}, ran {got}" for pin, want, got in drifted)
        raise PinDriftError(f"harness version drift: {detail}")


def _spent(records: list[TrialRecord]) -> tuple[float, bool]:
    known = all(
        r.reported_cost_usd is not None for r in records if r.status is not TrialStatus.ERROR
    )
    return sum(r.reported_cost_usd or 0.0 for r in records), known


def _arm(records: list[TrialRecord], pin: str) -> ArmSummary:
    mine = [r for r in records if r.pin == pin]
    return ArmSummary(
        pin=pin,
        n=sum(r.status is not TrialStatus.ERROR for r in mine),
        passes=sum(r.status is TrialStatus.PASS for r in mine),
        errors=sum(r.status is TrialStatus.ERROR for r in mine),
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


def _metrics(
    records: list[TrialRecord], baseline: str, candidate: str, loaded: LoadedConfig
) -> list[RatioEstimate]:
    stats = loaded.config.stats
    out = []
    for i, (metric, attr) in enumerate(METRICS.items()):
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


def run_compare(
    loaded: LoadedConfig,
    suite: Suite,
    runner: Runner,
    baseline: str,
    candidate: str,
    *,
    max_usd: float | None = None,
    max_batches: int | None = None,
) -> RunOutcome:
    cfg = loaded.config
    if baseline == candidate:
        raise ValueError("baseline and candidate must be different pins")
    pins = {baseline: loaded.pin(baseline), candidate: loaded.pin(candidate)}
    budget_usd = cfg.budget.max_usd if max_usd is None else max_usd
    batch_limit = cfg.budget.max_batches if max_batches is None else max_batches
    alternative, alpha = cfg.stats.alternative, cfg.stats.alpha

    manifest = _manifest(
        loaded, suite, runner, pins, kind="compare", baseline=baseline, candidate=candidate
    )
    bundle = RunBundle.create(runs_dir(loaded.home), manifest)
    log.info(
        "compare started",
        extra={"run_id": bundle.run_id, "baseline": baseline, "candidate": candidate},
    )

    records: list[TrialRecord] = []
    state = SequentialState(q_max=cfg.stats.mixture_max)
    history: list[BatchPoint] = []
    stop_reason: str | None = None
    warned_unknown_cost = False
    try:
        for batch in range(batch_limit):
            spent, cost_known = _spent(records)
            if batch > 0 and cost_known and spent + spent / batch > budget_usd:
                stop_reason = "budget_usd"
                break
            if not cost_known and not warned_unknown_cost:
                log.warning("some trials report no cost; the dollar cap cannot be enforced")
                warned_unknown_cost = True
            new = runner.run_batch(
                BatchRequest(
                    batch=batch,
                    tasks=suite.tasks,
                    pins=pins,
                    attempts=cfg.budget.attempts_per_batch,
                    bundle_dir=bundle.path,
                )
            )
            bundle.append_trials(new)
            records.extend(new)
            _check_drift(new, pins)

            batch_pairs, _ = build_pairs(new, baseline, candidate)
            state = state.update(batch_pairs, alternative)
            spent, _ = _spent(records)
            point = BatchPoint(
                batch=batch,
                n_pairs=state.n_pairs,
                n_discordant=state.n_discordant,
                n_regress=state.n_regress,
                n_improve=state.n_improve,
                e_value=state.e(alternative),
                spent_usd=round(spent, 6),
            )
            history.append(point)
            log.info("batch evaluated", extra=point.model_dump())
            if state.decision(alternative, alpha) != "inconclusive":
                stop_reason = "significant"
                break
        else:
            stop_reason = "max_batches"
    except Exception:
        log.exception("compare aborted; sealing partial bundle", extra={"run_id": bundle.run_id})
        bundle.seal()
        RunIndex(index_path(loaded.home)).ingest(bundle)
        raise

    _, dropped = build_pairs(records, baseline, candidate)
    spent, cost_known = _spent(records)
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
    loaded: LoadedConfig, suite: Suite, runner: Runner, pin: str, *, attempts: int
) -> RunOutcome:
    pins = {pin: loaded.pin(pin)}
    bundle = RunBundle.create(
        runs_dir(loaded.home), _manifest(loaded, suite, runner, pins, kind="run")
    )
    try:
        records = runner.run_batch(
            BatchRequest(
                batch=0, tasks=suite.tasks, pins=pins, attempts=attempts, bundle_dir=bundle.path
            )
        )
        bundle.append_trials(records)
        _check_drift(records, pins)
    finally:
        bundle.seal()
    RunIndex(index_path(loaded.home)).ingest(bundle)
    return RunOutcome(bundle=bundle, verdict=None)
