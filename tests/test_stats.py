from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.integrate import quad

from agent_canary.models import TrialStatus
from agent_canary.stats import (
    SequentialState,
    build_pairs,
    cluster_bootstrap_ratio,
    e_value,
    log_e_one_sided,
    min_discordant_to_detect,
)
from tests.conftest import record

# ---------------------------------------------------------------------------- e-process maths


def test_e_is_one_before_any_evidence() -> None:
    assert log_e_one_sided(0, 0) == pytest.approx(0.0)


@pytest.mark.parametrize(("n", "k"), [(1, 0), (1, 1), (5, 3), (10, 9), (20, 4), (40, 30)])
def test_closed_form_matches_numerical_integral(n: int, k: int) -> None:
    integral, _ = quad(lambda q: q**k * (1 - q) ** (n - k), 0.5, 1.0)
    expected = math.log(2 ** (n + 1) * integral)
    assert log_e_one_sided(n, k) == pytest.approx(expected, rel=1e-9, abs=1e-12)


@pytest.mark.parametrize(
    ("n", "k", "q_max"), [(5, 3, 0.8), (20, 14, 0.7), (40, 25, 0.75), (8, 8, 0.6)]
)
def test_truncated_mixture_matches_numerical_integral(n: int, k: int, q_max: float) -> None:
    integral, _ = quad(lambda q: q**k * (1 - q) ** (n - k), 0.5, q_max)
    expected = math.log(2**n * integral / (q_max - 0.5))
    assert log_e_one_sided(n, k, q_max) == pytest.approx(expected, rel=1e-9, abs=1e-12)


def test_invalid_mixture_bound_rejected() -> None:
    with pytest.raises(ValueError, match="q_max"):
        log_e_one_sided(3, 1, 0.5)


def test_seven_straight_regressions_needed_at_alpha_005() -> None:
    assert min_discordant_to_detect(0.05) == 7
    assert e_value(6, 0, "less") < 20 <= e_value(7, 0, "less")


def test_improvements_push_regression_evidence_down() -> None:
    assert e_value(5, 5, "less") < 1.0
    assert e_value(0, 7, "greater") >= 20


def test_two_sided_is_average_of_one_sided() -> None:
    assert e_value(4, 1, "two-sided") == pytest.approx(
        0.5 * (e_value(4, 1, "less") + e_value(4, 1, "greater"))
    )


def test_large_counts_do_not_overflow() -> None:
    assert math.isfinite(e_value(5000, 0, "less"))


def test_invalid_counts_rejected() -> None:
    with pytest.raises(ValueError, match="0 <= k <= n"):
        log_e_one_sided(3, 4)


# ---------------------------------------------------------------------------- error control


def _simulate_rejections(
    a: np.ndarray,
    b: np.ndarray,
    *,
    n_sims: int,
    n_batches: int,
    alpha: float,
    seed: int,
    q_max: float = 1.0,
) -> float:
    """Fraction of simulated compare runs that ever cross 1/alpha at a batch boundary."""
    rng = np.random.default_rng(seed)
    base = rng.random((n_sims, n_batches, a.size)) < a
    cand = rng.random((n_sims, n_batches, b.size)) < b
    regress = np.cumsum((base & ~cand).sum(axis=2), axis=1)
    improve = np.cumsum((~base & cand).sum(axis=2), axis=1)
    threshold = math.log(1 / alpha)
    rejected = np.zeros(n_sims, dtype=bool)
    cache: dict[tuple[int, int], bool] = {}
    for s in range(n_sims):
        for t in range(n_batches):
            key = (int(regress[s, t] + improve[s, t]), int(regress[s, t]))
            if key not in cache:
                cache[key] = log_e_one_sided(*key, q_max) >= threshold
            if cache[key]:
                rejected[s] = True
                break
    return float(rejected.mean())


def test_false_alarm_rate_under_identical_arms() -> None:
    a = np.array([0.95, 0.9, 0.7, 0.5, 0.3, 0.1, 0.6, 0.8])
    rate = _simulate_rejections(a, a, n_sims=3000, n_batches=40, alpha=0.05, seed=1)
    assert rate <= 0.05 + 0.012  # alpha plus ~3 Monte Carlo standard errors


@pytest.mark.parametrize("q_max", [1.0, 0.75])
def test_false_alarm_rate_under_heterogeneous_null(q_max: float) -> None:
    """Candidate better on some tasks, worse on others, equal on average (ADR-0003)."""
    a = np.array([0.9, 0.2, 0.8, 0.3, 0.6, 0.5])
    b = np.array([0.2, 0.9, 0.3, 0.8, 0.5, 0.6])
    assert a.mean() == pytest.approx(b.mean())
    rate = _simulate_rejections(a, b, n_sims=3000, n_batches=40, alpha=0.05, seed=2, q_max=q_max)
    assert rate <= 0.05 + 0.012


def test_detects_a_real_regression() -> None:
    a = np.array([0.9, 0.85, 0.8, 0.9, 0.7, 0.95, 0.75, 0.8])
    rate = _simulate_rejections(a, a - 0.35, n_sims=1000, n_batches=10, alpha=0.05, seed=3)
    assert rate >= 0.9


# ---------------------------------------------------------------------------- sequential state


def test_state_tracks_running_max_for_anytime_p() -> None:
    from agent_canary.stats import Pair

    regress_pairs = [Pair(0, f"t{i}", True, False) for i in range(5)]
    improve_pairs = [Pair(1, f"t{i}", False, True) for i in range(5)]
    s1 = SequentialState().update(regress_pairs, "less")
    s2 = s1.update(improve_pairs, "less")
    assert s2.e("less") < s1.e("less")
    assert s2.p_value() == pytest.approx(1 / s1.e("less"))
    assert s2.decision("less", 0.05) == "inconclusive"


def test_two_sided_decision_picks_direction() -> None:
    from agent_canary.stats import Pair

    pairs = [Pair(0, f"t{i}", False, True) for i in range(12)]
    state = SequentialState().update(pairs, "two-sided")
    assert state.decision("two-sided", 0.05) == "improvement"


# ---------------------------------------------------------------------------- pairing


def test_pairs_match_task_and_batch() -> None:
    records = [
        record(task="x", pin="base", batch=0, status=TrialStatus.PASS),
        record(task="x", pin="cand", batch=0, status=TrialStatus.FAIL),
        record(task="x", pin="cand", batch=1, status=TrialStatus.PASS),  # no partner
        record(task="y", pin="base", batch=0, status=TrialStatus.ERROR),
        record(task="y", pin="cand", batch=0, status=TrialStatus.PASS),
        record(task="z", pin="other", batch=0),
    ]
    pairs, dropped = build_pairs(records, "base", "cand")
    assert [(p.task, p.regress) for p in pairs] == [("x", True)]
    assert dropped == 2


def test_multiple_attempts_pair_in_name_order() -> None:
    records = [
        record(task="x", pin="b", name="x-2", status=TrialStatus.FAIL),
        record(task="x", pin="b", name="x-1", status=TrialStatus.PASS),
        record(task="x", pin="c", name="x-4", status=TrialStatus.PASS),
        record(task="x", pin="c", name="x-3", status=TrialStatus.FAIL),
    ]
    pairs, dropped = build_pairs(records, "b", "c")
    assert dropped == 0
    assert [(p.baseline_pass, p.candidate_pass) for p in pairs] == [(True, False), (False, True)]


# ---------------------------------------------------------------------------- bootstrap

_KW = {"n_resamples": 2000, "confidence": 0.95, "seed": 7, "threshold": 0.10}


def test_bootstrap_identical_arms_ci_contains_one() -> None:
    rng = np.random.default_rng(0)
    data = {f"t{i}": list(rng.lognormal(0, 0.3, 4) * (i + 1)) for i in range(12)}
    est = cluster_bootstrap_ratio("cost_usd", data, data, **_KW)
    assert est is not None
    assert est.ratio == pytest.approx(1.0)
    assert est.ci_low <= 1.0 <= est.ci_high
    assert not est.flagged


def test_bootstrap_flags_clear_increase_and_is_deterministic() -> None:
    rng = np.random.default_rng(1)
    base = {f"t{i}": list(rng.lognormal(0, 0.2, 3) * (i + 1)) for i in range(15)}
    cand = {t: [v * 1.6 for v in vals] for t, vals in base.items()}
    first = cluster_bootstrap_ratio("cost_usd", base, cand, **_KW)
    second = cluster_bootstrap_ratio("cost_usd", base, cand, **_KW)
    assert first is not None
    assert first == second
    assert first.ratio == pytest.approx(1.6)
    assert first.flagged


def test_bootstrap_uses_only_tasks_present_in_both_arms() -> None:
    est = cluster_bootstrap_ratio("x", {"a": [1.0], "b": [100.0]}, {"a": [2.0]}, **_KW)
    assert est is not None
    assert est.ratio == pytest.approx(2.0)
    assert est.n_baseline == 1


def test_bootstrap_returns_none_without_data() -> None:
    assert cluster_bootstrap_ratio("x", {}, {"a": [1.0]}, **_KW) is None
    assert cluster_bootstrap_ratio("x", {"a": [0.0]}, {"a": [1.0]}, **_KW) is None
