"""Power simulation for the pass-rate test: runs and dollars to detect a regression.

Costs nothing: outcomes are simulated, not run. It sizes the regression-injection benchmark
before we spend on it, and checks ADR-0003's claims against two alternatives:

- e-process(q)  the canary's paired mixture e-process with mixture bound q_max, checked after
                every batch (ADR-0003)
- fixed-N       an exact one-sided McNemar test, run once at the full budget
- peeking       the same McNemar test re-checked after every batch, stopping at p < alpha. This is
                what a naive canary does; it inflates false alarms.

Model: each task has a latent difficulty d ~ N(0, spread) on the logit scale, shared by both
arms. Baseline pass probability is sigmoid(logit(p0) + d). The candidate is shifted on the logit
scale by the amount that lowers the suite-average pass rate by `drop` points. Every batch runs each
task once per arm (a full sweep), exactly like `canary compare` with attempts_per_batch = 1. A
fresh suite is drawn for every simulated run, so results average over suites.

    uv run python benchmarks/power_simulation.py            # writes benchmarks/results/
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logit
from scipy.stats import binom

from agent_canary.stats import log_e_one_sided

RESULTS = Path(__file__).parent / "results"


@dataclass(frozen=True)
class EprocResult:
    q_max: float
    detect_rate: float
    median_batches: float | None
    mean_trials: float


@dataclass(frozen=True)
class Outcome:
    n_tasks: int
    drop: float
    eproc: list[EprocResult]
    fixed_detect_rate: float
    peek_detect_rate: float
    discordance: float


class _Tests:
    """Memoised statistics keyed by cumulative (n discordant, k regressions)."""

    def __init__(self, alpha: float, q_maxes: list[float]) -> None:
        self.log_threshold = math.log(1.0 / alpha)
        self.alpha = alpha
        self.q_maxes = q_maxes
        self._e: dict[tuple[int, int, float], bool] = {}
        self._p: dict[tuple[int, int], bool] = {}

    def e_rejects(self, n: int, k: int, q_max: float) -> bool:
        key = (n, k, q_max)
        if key not in self._e:
            self._e[key] = log_e_one_sided(n, k, q_max) >= self.log_threshold
        return self._e[key]

    def mcnemar_rejects(self, n: int, k: int) -> bool:
        key = (n, k)
        if key not in self._p:
            # One-sided exact McNemar: P(X >= k | n discordant, q = 1/2) < alpha.
            self._p[key] = n > 0 and float(binom.sf(k - 1, n, 0.5)) < self.alpha
        return self._p[key]


def _shift_for_drop(base_logits: np.ndarray, drop: float) -> float:
    if drop == 0:
        return 0.0
    target = expit(base_logits).mean() - drop
    return float(brentq(lambda s: expit(base_logits - s).mean() - target, 0.0, 20.0))


def simulate(
    n_tasks: int,
    drop: float,
    *,
    p0: float,
    spread: float,
    max_batches: int,
    n_sims: int,
    rng: np.random.Generator,
    tests: _Tests,
) -> Outcome:
    base_logits = logit(p0) + rng.normal(0.0, spread, size=(n_sims, n_tasks))
    shifts = np.array([_shift_for_drop(row, drop) for row in base_logits])
    pa = expit(base_logits)
    pb = expit(base_logits - shifts[:, None])

    shape = (n_sims, max_batches, n_tasks)
    base = rng.random(shape) < pa[:, None, :]
    cand = rng.random(shape) < pb[:, None, :]
    regress = np.cumsum((base & ~cand).sum(axis=2), axis=1)
    discordant = regress + np.cumsum((~base & cand).sum(axis=2), axis=1)

    stops = {q: np.full(n_sims, -1) for q in tests.q_maxes}
    peek = np.zeros(n_sims, dtype=bool)
    for s in range(n_sims):
        for t in range(max_batches):
            n, k = int(discordant[s, t]), int(regress[s, t])
            for q in tests.q_maxes:
                if stops[q][s] < 0 and tests.e_rejects(n, k, q):
                    stops[q][s] = t
            peek[s] |= tests.mcnemar_rejects(n, k)
    fixed = np.array(
        [tests.mcnemar_rejects(int(discordant[s, -1]), int(regress[s, -1])) for s in range(n_sims)]
    )

    eproc = []
    for q in tests.q_maxes:
        detected = stops[q] >= 0
        used = np.where(detected, stops[q] + 1, max_batches)
        eproc.append(
            EprocResult(
                q_max=q,
                detect_rate=float(detected.mean()),
                median_batches=float(np.median(stops[q][detected] + 1)) if detected.any() else None,
                mean_trials=float(used.mean() * 2 * n_tasks),
            )
        )
    return Outcome(
        n_tasks=n_tasks,
        drop=drop,
        eproc=eproc,
        fixed_detect_rate=float(fixed.mean()),
        peek_detect_rate=float(peek.mean()),
        discordance=float((pa * (1 - pb) + (1 - pa) * pb).mean()),
    )


def render(outcomes: list[Outcome], args: argparse.Namespace) -> str:
    qs = args.mixture_max
    head = " | ".join(f"e-process q≤{q:g}" for q in qs)
    lines = [
        "# Power simulation: pass-rate regression detection",
        "",
        f"**Simulated, not measured.** Seed {args.seed}; {args.sims} simulated compare runs per "
        f"row; alpha = {args.alpha}; budget = {args.max_batches} batches; baseline pass rate "
        f"centred on {args.p0:.0%} with task spread sigma = {args.spread} on the logit scale; one "
        f"attempt per task per arm per batch. Dollars assume ${args.cost_per_trial:.2f} per "
        "trial, a placeholder until measured harness costs replace it.",
        "",
        "Each e-process cell: detection rate within budget / median batches to detection / "
        "mean spend including runs that never detect. Rows with `drop = 0` are false-alarm rates "
        "and should be at or below alpha.",
        "",
        f"| Tasks | Drop | {head} | Fixed-N McNemar | McNemar re-checked each batch "
        "| Discordance |",
        "|---:|---:|" + "---:|" * len(qs) + "---:|---:|---:|",
    ]
    for o in outcomes:
        cells = []
        for e in o.eproc:
            med = f"{e.median_batches:.0f}" if e.median_batches is not None else "—"
            cells.append(
                f"{e.detect_rate:.1%} / {med} / ${e.mean_trials * args.cost_per_trial:,.0f}"
            )
        lines.append(
            f"| {o.n_tasks} | {o.drop:.0%} | {' | '.join(cells)} | {o.fixed_detect_rate:.1%} | "
            f"{o.peek_detect_rate:.1%} | {o.discordance:.2f} |"
        )
    lines += [
        "",
        "How to read it:",
        "",
        "- **False alarms (drop = 0).** Re-checking a fixed-sample test after every batch is what "
        "a naive canary does. Compare its false-alarm rate with the e-process columns.",
        "- **Power.** The fixed-N test gets one look at the full budget and always pays for all of "
        "it. The e-process pays only until it is sure.",
        "- **Mixture bound.** A lower q_max concentrates evidence on small regressions, the ones "
        "that matter for a canary. Every bound keeps the false-alarm guarantee (ADR-0003).",
        "- **Discordance** is the share of task-batches where the two arms disagree. Only those "
        "carry evidence, so tasks that always pass or always fail cost money for nothing.",
        "",
        "Regenerate with `uv run python benchmarks/power_simulation.py`.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Power simulation for the pass-rate test.")
    parser.add_argument("--sims", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260927)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--p0", type=float, default=0.6)
    parser.add_argument("--spread", type=float, default=1.5)
    parser.add_argument("--max-batches", type=int, default=20)
    parser.add_argument("--cost-per-trial", type=float, default=0.50)
    parser.add_argument("--tasks", type=int, nargs="+", default=[10, 25, 50])
    parser.add_argument("--drops", type=float, nargs="+", default=[0.0, 0.05, 0.10, 0.20])
    parser.add_argument("--mixture-max", type=float, nargs="+", default=[1.0, 0.8, 0.7])
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    tests = _Tests(args.alpha, args.mixture_max)
    outcomes = [
        simulate(
            t,
            d,
            p0=args.p0,
            spread=args.spread,
            max_batches=args.max_batches,
            n_sims=args.sims,
            rng=rng,
            tests=tests,
        )
        for t in args.tasks
        for d in args.drops
    ]
    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {"args": vars(args), "outcomes": [asdict(o) for o in outcomes]}
    (RESULTS / "power-simulation.json").write_text(json.dumps(payload, indent=2) + "\n")
    report = render(outcomes, args)
    (RESULTS / "power-simulation.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
