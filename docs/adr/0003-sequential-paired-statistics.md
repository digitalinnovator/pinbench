# ADR-0003: Paired, anytime-valid sequential test on pass rate; cluster bootstrap on cost

- Status: Accepted
- Date: 2026-09-27

## Context

Every trial of a coding agent costs real tokens and minutes. The canary has to answer "is the candidate pin worse than the baseline?" with a known false-alarm rate, and stop spending as soon as the answer is clear. Four features of the data shape the design:

1. **Outcomes are nondeterministic.** The same task, harness and model can pass one run and fail the next.
2. **Tasks differ hugely in difficulty.** Pooling all trials into one Bernoulli rate throws away the pairing and inflates variance.
3. **The API drifts over time.** A baseline measured last week is not a clean control for a candidate measured today.
4. **People peek.** A canary that checks results after every batch and stops early breaks fixed-sample tests. Repeatedly applying a t-test or a Fisher test inflates the false-alarm rate far above the nominal α.

## Decision

### Design: concurrent, paired batches

Each batch runs every task in the suite `k` times on both the baseline and the candidate, in the same Harbor job (ADR-0002). Trials pair up by task within a batch. This controls for task difficulty through pairing, and for API drift through concurrency.

### Pass rate: a mixture e-process on discordant pairs, checked at batch boundaries

For a pair, let `D = 1` if the baseline passed and the candidate failed (a regression), and `D = 0` if the reverse happened. Concordant pairs, where both passed or both failed, carry no information about the difference and are skipped. After `n` discordant pairs, `k` of them regressions, the one-sided test for "candidate is worse" uses a uniform mixture over `q ∈ [½, 1]`:

```
E_n = 2^(n+1) · ∫_{½}^{1} q^k (1-q)^(n-k) dq
    = 2^(n+1) · B(k+1, n-k+1) · I_{½}(n-k+1, k+1)
```

The canary raises a regression alarm when `E_n ≥ 1/α` (default α = 0.05, so a threshold of 20). It reports the anytime-valid p-value `p = min(1, 1 / max_b E_b)`.

**Why this is valid under optional stopping.** For a fixed `q > ½`, consider the likelihood-ratio product over one full batch. Task `t` has baseline pass probability `a_t` and candidate pass probability `b_t`. Because the tasks run independently, the expected value of that product is

```
∏_t (1 + (2q-1)(a_t - b_t))  ≤  (1 + (2q-1)·mean_t(a_t - b_t))^T  ≤  1
```

by the AM–GM inequality, whenever `mean_t b_t ≥ mean_t a_t`. This uses the identity `P(D=1) - P(D=0) = a_t(1-b_t) - (1-a_t)b_t = a_t - b_t`. So, **sampled at batch boundaries**, the process is a non-negative supermartingale under the null "the candidate's average pass rate over the suite is not lower". Mixing over `q` preserves this property. Ville's inequality then bounds the chance of ever crossing `1/α` under the null by α, whenever the canary stops.

This is a real statistical requirement for the code, not only a style choice:

- Stopping is only evaluated at batch boundaries.
- A batch must be a full sweep of the suite: every task, `k` times, on each arm.

Checking in the middle of a batch would only be valid under the stronger null "no task got worse".

`E_n` depends only on `(n, k)`, so the state is two integers. The test needs no effect size in advance, which Wald's SPRT would.

Two-sided detection ("changed in either direction") averages the two one-sided e-processes, `E = (E_less + E_greater) / 2`, which is itself an e-process. The default is one-sided (regression), because that is the alarm the canary exists to raise.

### Stopping rules

The canary stops at the first batch boundary where any of these holds:

- `E ≥ 1/α`: regression detected.
- The budget is exhausted, in dollars or batches (ADR-0004 records spend). The verdict is then "inconclusive at this budget". It is never "no regression".

### Tokens, dollars and latency: cluster bootstrap on the ratio of means

For each metric (cost in USD, input tokens, output tokens, agent wall time), the canary reports `mean(candidate) / mean(baseline)` with a percentile confidence interval. The interval comes from a **cluster bootstrap over tasks**: resample task IDs with replacement, and keep all trials of a resampled task in both arms. The canary flags a cost regression when the lower bound exceeds 1.0 and the point estimate exceeds `1 + threshold` (default 10%). It uses a fixed seed, recorded in the run bundle, so reports can be reproduced exactly.

### Amendment (2026-09-27): mixture bound q_max = 0.8

The first version mixed uniformly over `q ∈ [½, 1]`. The [power simulation](../../benchmarks/results/power-simulation.md) shows that this spreads evidence across implausibly large effects. A 10-point pass-rate drop at typical discordance is `q ≈ 0.64`. The mixture is now uniform over `[½, q_max]` with `q_max = 0.8` by default (`[stats] mixture_max`):

```
E_n = 2^n / (q_max - ½) · ∫_{½}^{q_max} q^k (1-q)^(n-k) dq
```

Any `q_max > ½` keeps the false-alarm guarantee, because every component of the mixture is a supermartingale under the null. What moves is power. Simulated results (2,000 runs per cell, 20-batch budget):

| Tasks | Drop | Detected, q ≤ 1 | Detected, q ≤ 0.8 | Mean spend, q ≤ 1 → 0.8 |
|---|---|---|---|---|
| 25 | 5 pts | 22.5% | 27.4% | $445 → $436 |
| 25 | 10 pts | 81.2% | 86.1% | $286 → $266 |
| 50 | 5 pts | 42.9% | 49.2% | $812 → $770 |
| 50 | 20 pts | 100%, median 2 batches | 100%, median 2 batches | $105 → $101 |

The price is a higher floor. At least 10 discordant pairs are needed to raise an alarm, up from 7. The same simulation measured two things that motivate this ADR:

- **Re-checking an exact McNemar test after every batch gives 14–19% false alarms** at a nominal 5%.
- **A single fixed-N McNemar test at the full budget has more power** (97% against 86% at 25 tasks, 10 points), but it always spends the whole budget.

## Consequences

- The false-alarm rate is controlled even though the canary checks after every batch. This is the property that lets it stop early and save money.
- Pairing and concurrency remove task-difficulty variance and time drift. The price is always running the baseline arm too, which roughly doubles cost per batch compared with testing against stored history. A future "history mode" can test against stored baselines for cheap daily monitoring, and accept the drift risk explicitly.
- Concordant pairs are wasted spend from the pass-rate test's point of view. Tasks the agent always passes or always fails add cost and no signal. The report shows discordance per task so users can prune suites.
- **The bootstrap intervals are not anytime-valid.** They are computed once, at the stopping time, and are optimistic if read after every batch. The report labels them as fixed-sample intervals at stop. A confidence-sequence replacement is on the roadmap.
- Infrastructure errors drop the pair: no verifier result, or an exception in `INFRASTRUCTURE_EXCEPTIONS` (`runners/harbor.py`), such as authentication, rate limiting, API outages or sandbox setup. Agent timeouts, context-window overflows, refusals and harness crashes count as failures, because a harness version can cause them. The guarantee assumes those drops are unrelated to the outcome. The report shows dropped pairs.
- Pass criteria are binary: reward ≥ threshold, default 1.0. Graded rewards need another test, which is on the roadmap.

## Alternatives considered

- **Fixed-sample tests (two-proportion z-test, Fisher, McNemar) at a pre-set N.** Valid only without peeking, and they waste budget on obvious regressions.
- **Wald's SPRT.** Optimal for a single specified alternative, but it needs an effect size up front and assumes identical trials. It loses power when the true effect is not the one assumed.
- **Group-sequential designs (O'Brien–Fleming, alpha spending).** They need a planned maximum number of looks, and the error control is less intuitive to explain in a README. The e-process tolerates unplanned extra batches.
- **Unpaired Bayesian A/B test on pooled pass rates.** It ignores task difficulty. Posterior thresholds do not bound the frequentist false-alarm rate that on-call engineers care about.
- **Per-task tests with multiple-comparison correction.** Low power on the small suites teams actually maintain (tens of tasks). This is kept as a drill-down in the report rather than as the alarm.

The regression-injection benchmark will compare the mixture e-process against SPRT and a fixed-N McNemar test on detection power per dollar. That comparison is the evidence behind this decision.
