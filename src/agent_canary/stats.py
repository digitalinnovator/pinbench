"""Statistics under nondeterminism (ADR-0003).

Pass rate: a paired, anytime-valid mixture e-process on discordant pairs, evaluated only at batch
boundaries. Cost, tokens and latency: cluster bootstrap over tasks on the ratio of means.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.special import betaincc, betaln

from agent_canary.models import RatioEstimate, TrialRecord, TrialStatus

Alternative = Literal["less", "greater", "two-sided"]
_LN2 = math.log(2.0)
_MAX_LOG_E = 700.0  # exp() overflows past ~709; any E this large is decisive anyway


# --------------------------------------------------------------------------------------------
# Pairing
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pair:
    batch: int
    task: str
    baseline_pass: bool
    candidate_pass: bool

    @property
    def regress(self) -> bool:
        return self.baseline_pass and not self.candidate_pass

    @property
    def improve(self) -> bool:
        return self.candidate_pass and not self.baseline_pass


def build_pairs(
    records: Iterable[TrialRecord], baseline: str, candidate: str
) -> tuple[list[Pair], int]:
    """Pair baseline and candidate trials of the same task within the same batch.

    Trials are matched in trial-name order, which is deterministic. A pair is dropped when either
    side errored or the two arms produced a different number of trials for that task and batch.
    Returns (pairs, dropped).
    """
    arms: dict[tuple[int, str], dict[str, list[TrialRecord]]] = defaultdict(
        lambda: {baseline: [], candidate: []}
    )
    for r in records:
        if r.pin in (baseline, candidate):
            arms[(r.batch, r.task)][r.pin].append(r)

    pairs: list[Pair] = []
    dropped = 0
    for (batch, task), by_pin in sorted(arms.items()):
        b = sorted(by_pin[baseline], key=lambda r: r.trial_name)
        c = sorted(by_pin[candidate], key=lambda r: r.trial_name)
        dropped += abs(len(b) - len(c))
        for rb, rc in zip(b, c, strict=False):
            if TrialStatus.ERROR in (rb.status, rc.status):
                dropped += 1
                continue
            pairs.append(
                Pair(
                    batch=batch,
                    task=task,
                    baseline_pass=rb.status is TrialStatus.PASS,
                    candidate_pass=rc.status is TrialStatus.PASS,
                )
            )
    return pairs, dropped


# --------------------------------------------------------------------------------------------
# Mixture e-process on discordant pairs
# --------------------------------------------------------------------------------------------


def log_e_one_sided(n: int, k: int, q_max: float = 1.0) -> float:
    """log E for "q > 1/2" after k successes in n discordant pairs.

    Uniform mixture over q in [1/2, q_max]:

    E_n = 2^n / (q_max - 1/2) * integral_{1/2}^{q_max} q^k (1-q)^(n-k) dq
        = 2^n / (q_max - 1/2) * B(k+1, n-k+1) * [Ic_{1/2} - Ic_{q_max}](k+1, n-k+1)

    where Ic is the complemented regularised incomplete beta function (upper tails, which avoids
    cancellation). Any mixture over q > 1/2 is a non-negative supermartingale under q <= 1/2 at
    full-sweep batch boundaries (ADR-0003), so P(sup E >= 1/alpha) <= alpha for every q_max.
    q_max only moves power between small and large effects.
    """
    if not 0 <= k <= n:
        raise ValueError(f"need 0 <= k <= n, got k={k}, n={n}")
    if not 0.5 < q_max <= 1.0:
        raise ValueError(f"q_max must be in (0.5, 1], got {q_max}")
    a, b = k + 1, n - k + 1
    tail = float(betaincc(a, b, 0.5)) - (float(betaincc(a, b, q_max)) if q_max < 1.0 else 0.0)
    if tail <= 0.0:
        return -math.inf
    return n * _LN2 - math.log(q_max - 0.5) + float(betaln(a, b)) + math.log(tail)


def _exp(x: float) -> float:
    return math.exp(min(x, _MAX_LOG_E))


def e_value(n_regress: int, n_improve: int, alternative: Alternative, q_max: float = 1.0) -> float:
    """E-value for the chosen alternative from cumulative discordant-pair counts."""
    n = n_regress + n_improve
    e_less = _exp(log_e_one_sided(n, n_regress, q_max))  # candidate worse
    e_greater = _exp(log_e_one_sided(n, n_improve, q_max))  # candidate better
    if alternative == "less":
        return e_less
    if alternative == "greater":
        return e_greater
    return 0.5 * (e_less + e_greater)


@dataclass(frozen=True)
class SequentialState:
    """Cumulative state of the pass-rate test at a batch boundary."""

    q_max: float = 1.0
    n_pairs: int = 0
    n_regress: int = 0
    n_improve: int = 0
    max_e: float = 1.0

    @property
    def n_discordant(self) -> int:
        return self.n_regress + self.n_improve

    def update(self, batch_pairs: Sequence[Pair], alternative: Alternative) -> SequentialState:
        n_regress = self.n_regress + sum(p.regress for p in batch_pairs)
        n_improve = self.n_improve + sum(p.improve for p in batch_pairs)
        e = e_value(n_regress, n_improve, alternative, self.q_max)
        return SequentialState(
            q_max=self.q_max,
            n_pairs=self.n_pairs + len(batch_pairs),
            n_regress=n_regress,
            n_improve=n_improve,
            max_e=max(self.max_e, e),
        )

    def e(self, alternative: Alternative) -> float:
        return e_value(self.n_regress, self.n_improve, alternative, self.q_max)

    def p_value(self) -> float:
        """Anytime-valid p-value from the running maximum of E."""
        return min(1.0, 1.0 / self.max_e)

    def decision(
        self, alternative: Alternative, alpha: float
    ) -> Literal["regression", "improvement", "inconclusive"]:
        if self.e(alternative) < 1.0 / alpha:
            return "inconclusive"
        if alternative == "less":
            return "regression"
        if alternative == "greater":
            return "improvement"
        return "regression" if self.n_regress > self.n_improve else "improvement"


def min_discordant_to_detect(alpha: float, q_max: float = 1.0) -> int:
    """Smallest n such that n regressions out of n discordant pairs crosses 1/alpha."""
    threshold = math.log(1.0 / alpha)
    n = 0
    while log_e_one_sided(n, n, q_max) < threshold:
        n += 1
    return n


# --------------------------------------------------------------------------------------------
# Cluster bootstrap on ratio of means
# --------------------------------------------------------------------------------------------


def cluster_bootstrap_ratio(
    metric: str,
    baseline: Mapping[str, Sequence[float]],
    candidate: Mapping[str, Sequence[float]],
    *,
    n_resamples: int,
    confidence: float,
    seed: int,
    threshold: float,
) -> RatioEstimate | None:
    """mean(candidate) / mean(baseline) with a percentile CI from resampling tasks.

    Only tasks with observations in both arms are used, so the ratio compares like with like.
    Returns None when there is nothing to compare or the baseline mean is zero.
    """
    tasks = sorted(t for t in baseline if baseline[t] and candidate.get(t))
    if not tasks:
        return None
    b_sum = np.array([sum(baseline[t]) for t in tasks], dtype=float)
    b_cnt = np.array([len(baseline[t]) for t in tasks], dtype=float)
    c_sum = np.array([sum(candidate[t]) for t in tasks], dtype=float)
    c_cnt = np.array([len(candidate[t]) for t in tasks], dtype=float)

    b_mean = b_sum.sum() / b_cnt.sum()
    c_mean = c_sum.sum() / c_cnt.sum()
    if b_mean <= 0:
        return None

    rng = np.random.default_rng(seed)
    n_tasks = len(tasks)
    # Each row: how many times each task is drawn in one resample.
    weights = rng.multinomial(n_tasks, np.full(n_tasks, 1.0 / n_tasks), size=n_resamples)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratios = ((weights @ c_sum) / (weights @ c_cnt)) / ((weights @ b_sum) / (weights @ b_cnt))
    ratios = ratios[np.isfinite(ratios)]
    tail = (1.0 - confidence) / 2.0
    lo, hi = np.quantile(ratios, [tail, 1.0 - tail])
    ratio = c_mean / b_mean
    return RatioEstimate(
        metric=metric,
        baseline_mean=float(b_mean),
        candidate_mean=float(c_mean),
        ratio=float(ratio),
        ci_low=float(lo),
        ci_high=float(hi),
        n_baseline=int(b_cnt.sum()),
        n_candidate=int(c_cnt.sum()),
        flagged=bool(lo > 1.0 and ratio > 1.0 + threshold),
    )


METRICS: dict[str, str] = {
    "cost_usd": "reported_cost_usd",
    "input_tokens": "n_input_tokens",
    "output_tokens": "n_output_tokens",
    "agent_seconds": "agent_seconds",
}


def metric_by_task(records: Iterable[TrialRecord], pin: str, attr: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for r in records:
        if r.pin != pin or r.status is TrialStatus.ERROR:
            continue
        value = getattr(r, attr)
        if value is not None:
            out[r.task].append(float(value))
    return dict(out)
