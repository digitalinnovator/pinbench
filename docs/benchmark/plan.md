# Benchmark plan: regression-injection detection on a fixed small budget

> The project was renamed from "agent canary" to **pinbench** on 2026-10-21 ([ADR-0010](../adr/0010-name-pinbench.md)). This record keeps the names used at the time: `canary` is now `pinbench`, and `canary.toml` is `pinbench.toml`.

The benchmark is the launch (see the portfolio principles). This plan fixes the protocol before any money is spent, so the published numbers cannot be tuned after the fact.

- Status: **draft, not yet approved by the owner.** Nothing in it has been spent.
- Revised 2026-09-30, and again on 2026-10-19 after a free pre-screen of the tasks. The first version assumed $0.50 per trial and $5k–10k in total. Real trials cost far less, and the available credit is small, so the design below replaces it.

## Question

For a harness-layer regression of the kind in Anthropic's 2026-04-23 postmortem, does the canary flag it on a small private-style suite, and what did that one run cost?

This is a smaller question than the first version asked. It cannot be answered with "how many runs it takes" from the budget below: that needs replications.

## Budget

Two separate pools. Dollars in one cannot pay for trials in the other.

| Pool | Expected spend | Hard limit in the tool |
|---|---|---|
| Anthropic | $13–17, plus up to $4.50 for the optional step 7 | $22.50 |
| OpenAI | about $0.20 | $9.00 |

- **Expected** depends on what the headline run finds (see step 5). Every figure is an estimate until steps 1 and 4 measure real prices on the models used.
- **Hard limit** is enforced by a campaign ledger that does not exist yet (see "Build first"). Until it exists, nothing is run.
- Development work runs on a separate subscription and draws on neither pool.

## What the measurements say

All from 2026-09-30. Sources are the 15 real trials of spike 0001, the repo's price table, and simulations with the project's own decision rule. Nothing has been measured on Sonnet 5, Haiku 4.5 or any OpenAI model.

**Cost per trial** (demo-sized tasks, re-priced from the measured Opus 5 token counts; assumes a cheaper model uses as many requests, which is unverified):

| Model | Baseline, warm cache | Low effort, warm | Caching disabled |
|---|---|---|---|
| Opus 5 | $0.093 | $0.052 | $0.434 |
| Sonnet 5 | $0.037 | $0.021 | $0.174 |
| Haiku 4.5 | $0.0185 | $0.010 | $0.087 |

Tasks with headroom need more requests. The planning price is **$0.075 per Sonnet 5 trial** (twice the demo figure), with $0.116 as the stress case.

**Which knob works on which model:**

- Claude Code drops `--effort` silently on Haiku 4.5. The low-effort arm is only a real injection on Sonnet 5 or an Opus model.
- The caching and system-prompt injections do not depend on the model, so they can run on Haiku 4.5.
- `--max-budget-usd` is a soft cap checked between messages. A capped trial is scored by the hidden tests on whatever it had finished, which is usually a failure, so a cap that binds more in one arm is itself a treatment. Both arms of a pass-rate comparison must use the same cap and the same `max_turns`.

**Power (simulated, 20,000 runs per cell, shipped e-process at α = 0.05 and mixture bound 0.8):**

| Suite | Batch cap | Trials at cap | 25-point drop | 40-point drop |
|---|---|---|---|---|
| 18 tasks | 4 | 144 | 72–85% | 99–100% |
| 18 tasks | 5 | 180 | 83–93% | 100% |
| 18 tasks | 6 | 216 | 91–97% | 100% |

- A 15-point drop is not reliably detectable at any size this budget allows. The best cell simulated (24 tasks, 6 batches, 288 trials) reaches 55–72%.

- These figures assume every task can drop. On the suite the selection rule is likely to produce (about 7 tasks with real headroom plus tasks that passed both calibration attempts), simulated power at 5 batches is about **70%** if the easier tasks drop 10 points and about **34%** if they do not move.
- An A/A run almost never alarms at this size (at most 0.5% in simulation). "No alarm in A/A" is therefore not evidence of a low false-alarm rate. The guarantee comes from the e-process; the simulated rate is at most about 1.7%.
- A futility look after batch 3 (stop unless regressions minus improvements is at least 4) costs under 1 point of power and cuts the cost of a no-effect run by about 40%. It is valid because the e-process is anytime-valid.
- **The size of the effect is unknown.** The only real evidence is Opus 5 passing 6 of 6 demo tasks at low effort. The headline run may end "not flagged".

## Build first (no spend)

**Status, 2026-10-19:** items 1–9 are built and tested: the guardrails ([ADR-0009](../adr/0009-spending-guardrails.md)) and a 32-task suite, of which 18 are selected ([prescreen.md](prescreen.md)). Item 10 (OpenAI) has prices and the cache-write field; the agent-timeout override is built; the Codex install and the code-mode transcript check are still open. Nothing is run until all of them exist and are tested. An audit of the spending path found that `max_usd` is not a bound today: batch 0 is never checked, a trial with no cost turns the check off, `canary run` has no dollar cap, and the demo config's worst case is about $10.

1. **Campaign ledger, one per pool.** An append-only file outside any suite's `.canary`, with a lifetime limit. Before every batch, including batch 0 and every `canary run`, reserve trials × (per-trial cap + an allowance for the request in flight). Settle to the actual cost afterwards. Keep the reservation if the batch crashes. Refuse to start when the reservation would pass the limit.
2. **Refuse a harness pin with no per-trial bound** (`max_budget_usd` for Claude Code; an agent timeout for harnesses with no dollar cap).
3. **Fail closed on unknown cost.** A trial with no cost is charged at its cap.
4. **Abort a dead batch.** Stop when a batch has no valid pairs or one arm is all errors. Treat "Credit balance is too low" as an infrastructure error.
5. **Pin `retry.max_retries = 0`** in the Harbor job config.
6. **`--dry-run`** on `compare`, `run` and `watch`: print trials per batch, the reservation, and what is left in the ledger.
7. **Futility look** in the compare loop, recorded as its own stop reason.
8. **Record cap hits per arm** (`error_max_budget_usd`, `error_max_turns`).
9. **Task suite.** 24 candidate tasks from the candidate list, in the demo tasks' format, with byte-identical Dockerfiles. Validate each with the zero-cost oracle and nop agents.
10. **For the OpenAI pool only:** OpenAI prices in the price table and the cache-write field Codex uses; an agent-timeout override; the Codex CLI installed in the image; `service_tier = "default"`; a check that the verifier reads Codex's code-mode transcripts.

Outside the tool, the owner sets what the tool cannot: auto-reload off on both accounts, and a workspace or project spend limit if the console offers one.

## Steps

Revised 2026-10-19 after the free pre-screen ([prescreen.md](prescreen.md)). The pre-screen replaced the paid task selection, so calibration shrinks to one baseline run on the selected tasks, and the calibration A/A run is dropped: at this size it almost never alarms, so it was never evidence of a low false-alarm rate.

In this order. After every step, reconcile the ledger against the provider console before the next command.

| # | Step | Model | Trials | Expected | Notes |
|---|---|---|---|---|---|
| 1 | Knob smoke tests: one trial each for baseline, terse prompt, caching off, turn cap, budget cap (Haiku); effort high and low (Sonnet) | Haiku 4.5, Sonnet 5 | 7 | $0.35 | Confirms each knob reaches the API and each cap ends a trial with its cost recorded |
| 2 | Two-version run through `canary watch --run`: 2.1.283 against the latest release, 3 demo tasks, at most 2 batches | Haiku 4.5 | 12 | $0.32 | First real use of one Harbor job per version |
| 3 | Old-build smoke test: 2.1.66, 2.1.85, 2.1.112, one trial each | Haiku 4.5 | 3 | $0.12 | Does each build still run against today's API? Not a replay of the incident |
| 4 | Calibration: `s5-high` once on the 18 selected tasks, with a loose cap | Sonnet 5 | 18 | about $1.80 | The real price per trial and the real baseline pass rate under Harbor. These trials never enter a test |
| 5 | **Headline:** `s5-high` against `s5-low`, 18 tasks, at most 5 batches, futility look after batch 3 | Sonnet 5 | 72–180 | $6–14 | Published whatever the verdict |
| 6 | Caching-off cost arm: 6 suite tasks, one batch, no warm-up exclusion | Haiku 4.5 | 12 | $1.30 | A cost ratio, not a pass-rate test |
| 7 | Leftover, only if the ledger shows $15.00 or less spent: one more batch of the headline if it ended inconclusive at its batch cap, else the terse-prompt arm for token ratios | — | — | up to $4.50 | Decided by this rule, not after looking at the result |

Expected total: about $10–18, depending on how early the headline stops.

**Revision after step 4 (2026-10-20, before step 5 runs).** Real trials cost $0.155 on average, twice the planning price, so 18 tasks fit only 2 batches. The headline instead uses the 10 tasks with the largest expected drop per dollar, ranked mechanically:

- **Rule:** for each of the 18 tasks, expected drop = shrunk pre-screen high-effort pass rate minus shrunk low-effort pass rate (Beta(1, 1) prior); expected cost = the step-4 trial cost × 1.65 (one high and one low trial, low assumed at 0.65× high). Keep the 10 with the largest ratio.
- **Selected:** `invoice-rounding`, `order-state-machine`, `glob-match`, `format-number`, `version-range-match`, `dedupe-contacts`, `money-split`, `iso-week-report`, `strip-comments`, `cli-short-flags`.
- **Design:** per-trial cap $0.30 on both arms (above every step-4 trial of these tasks; the dearest was $0.249), `max_turns = 20`, at most 5 batches, futility look after batch 3, `max_usd = 12` (five batches at the expected $2.30 each).
- **Simulated detection** (shrunk pre-screen rates, step-4 baseline included): 97% if the pre-screen's effect transfers fully, 76% at three quarters, 35% at half. Expected cost about $8.80; the ledger holds 5 batches even if every trial hits its cap.

**Gates:**

- **After step 1:** no infrastructure errors; effort appears in the Sonnet requests; the caching-off trial shows zero cache tokens; a capped trial ends with its cost recorded; the ledger agrees with the console within 5%. A Haiku trial costs at most $0.06 and a Sonnet trial at most $0.12.
- **After step 4:**
  - Set the headline's per-trial cap to about twice the dearest calibration trial, the same in both arms, between $0.15 and $0.25, with `max_turns = 20`.
  - Re-run the power simulation with the measured baseline pass rates in place of the pre-screen's high-effort rates.
  - Run the headline only if the simulated detection rate is at least 50% and `--dry-run` shows at least 4 batches fit the ledger. Otherwise stop and ask the owner.
- **Step 5:** one attempt. No retuning of tasks and no second try counted as the first.

The selection rule and the per-task pre-screen results are fixed in [prescreen.md](prescreen.md). Calibration trials never enter a test.

## OpenAI pool

| # | Step | Trials | Expected | Bound |
|---|---|---|---|---|
| X1 | Codex adapter spike on `gpt-6-luna`: one trial, then effort high against low on the 3 demo tasks | 7 | $0.07 | 120 s agent timeout, one trial at a time |
| X2 | OpenCode adapter spike on `gpt-6-luna` | 4 | $0.05 | the same |
| X3 | Spare trials for a re-run after a fix | 4 | $0.05 | the same |

- Codex and OpenCode have no per-trial dollar cap. The bound is the agent timeout, and the worst-case figure ($4.56 for these 15 trials, from an estimated runaway rate) is an estimate, not an enforced limit. That is why the ledger limit is $9.00 and not $14.
- Stop all OpenAI runs if any trial costs more than $0.05, or if the first trial is billed at the priority tier.
- **Optional, the owner's decision after X1:** a Codex effort comparison on 12 tasks, about $1.50–5.00. It is offered only if X1 shows a dearest trial under $0.03 and the verifier reads the transcripts.
- OpenAI prices were read from the official pricing page on 2026-09-30 and confirmed unchanged on 2026-10-18. Re-verify them before any spend.

## Codex replicated benchmark (OpenAI pool), fixed 2026-10-21 before its first run

One Claude Code run cannot say how often the canary detects a regression. Codex trials cost about $0.005, so the OpenAI pool can buy repeated runs. The effort cut is high against `none`: the Codex headroom check (step C1) showed high against low makes almost no difference on these tasks (98% against 94%), and a one-trial probe at `none` passed 11 of 18 against 18 of 18 at high.

- **Config:** `examples/benchmark-suite-codex/replicate.toml`: Codex 0.163.0 on `gpt-6-luna`, the same 18 tasks as the Claude Code pre-screen selection (chosen for Sonnet 5, not for Codex), one attempt per task per arm per batch, at most 6 batches, futility look after batch 3 (net 4), α = 0.05, mixture bound 0.8, warm-up batch excluded from cost metrics.
- **Detection:** 5 independent runs of `codex-high` against `codex-none`. Reported: how many of the 5 flag a regression; for each, the batch, trials and dollars at which it flagged; the pass rates.
- **False alarms:** 2 runs of `codex-high` against `codex-high-twin` (identical but for an inert environment marker). Reported: how many flag anything, and whether any cost or latency metric is flagged.
- **No other runs are counted,** and none of these is dropped or repeated. The probe and step C1 trials are not reused.
- **Caveats fixed in advance:** effort `none` is a far bigger cut than the postmortem's high-to-medium; `gpt-6-luna` is not the model the incident was on; 5 runs give a rough rate (with 5 of 5 the 95% interval still reaches down to 48%); 2 A/A runs say little about a 5% false-alarm rate, which comes from the e-process guarantee.
- **Budget:** expected about $3.70, worst case about $6.50, within the $8.35 left under the OpenAI ledger limit.

## What the results can support

- "One pre-registered run on Claude Code 2.1.283 with Sonnet 5 and 18 tasks: lowering reasoning effort from high to low was (or was not) flagged after T trials and $X."
- Power curves, labelled as simulated and re-run on the measured per-task pass rates.
- A measured cost ratio with caching disabled, on 6 tasks, with the caveat that intervals over few tasks are too narrow.
- The false-alarm guarantee of the e-process and its simulated rate. No A/A run is claimed.
- A first count of false-success claims across all real transcripts, with the flagged cases labelled by hand.
- That `canary watch --run` tested a real release, and whether three March–April builds still run.
- That the Codex and OpenCode adapters run, with their token and transcript shape.

## What they cannot support

- A measured detection rate or a measured false-alarm rate. Both need replications.
- "It takes N runs to detect": one run is one draw from a stopping-time distribution.
- Detection of drops under about 20 points.
- Anything about Opus-tier models. The incident was on one, and high to low is a stronger change than the real high to medium.
- The verbosity regression as a pass-rate result.
- That the canary would have caught the real incident. The timeline replay is not funded.
- Any Codex regression result, unless the optional comparison is run.

## Open decisions for the owner

1. Is a Sonnet 5 headline acceptable? The same design on Opus 5.5 costs about 1.6 times as much and does not fit.
2. Is "not flagged within 180 trials" an acceptable launch headline if that is the result?
3. Leftover credit: a replication of the headline run, or the terse-prompt token row?
4. The Codex effort comparison: run it, or stop at the adapter spikes?
5. Are auto-reload and auto-recharge off, and does either console offer a spend limit?
