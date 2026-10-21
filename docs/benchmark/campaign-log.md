# Benchmark campaign log

> The project was renamed from "agent canary" to **pinbench** on 2026-10-21 ([ADR-0010](../adr/0010-name-pinbench.md)). This record keeps the names used at the time: `canary` is now `pinbench`, and `canary.toml` is `pinbench.toml`.

Every paid step of the [plan](plan.md), in order, with what it cost and what it showed. Spend is the canary's ledger figure (`canary ledger status`); it was not reconciled against the provider consoles after the campaign.

| Pool | Ledger limit |
|---|---|
| Anthropic | $22.50 |
| OpenAI | $9.00 |

## Step 1: knob and cap smoke tests, 2026-10-19

Seven single trials of Claude Code 2.1.283 on the demo task `parse-duration` (config: `examples/smoke/canary.toml`). **Spend: $0.35** (expected $0.35, worst case $1.26). A first attempt the same day failed with "Invalid API key" at no cost; the key had been revoked and was replaced.

| Pin | What it checks | Result | Cost | Requests | Cache read / write | Output | Harness stop |
|---|---|---|---|---|---|---|---|
| `h45` | Haiku 4.5 baseline | pass | $0.047 | 7 | 150k / 11k | 3.5k | success |
| `h45-terse` | appended system prompt | pass | $0.053 | 4 | 65k / 24k | 3.3k | success |
| `h45-no-cache` | `DISABLE_PROMPT_CACHING=1` | pass | $0.082 | 3 | 0 / 0 | 3.2k | success |
| `h45-turn-cap` | `max_turns = 1` | fail | $0.011 | 1 | 20k / 0 | 1.8k | `error_max_turns` |
| `h45-spend-cap` | `max_budget_usd = 0.005` | fail | $0.016 | 1 | 17k / 3k | 2.0k | `error_max_budget_usd` |
| `s5-high` | Sonnet 5, effort high | pass | $0.059 | 3 | 75k / 11k | 1.7k | success |
| `s5-low` | Sonnet 5, effort low | pass | $0.087 | 3 | 55k / 28k | 0.5k | success |

Gate checks (plan, after step 1):

- **No infrastructure errors.** Pass.
- **Each knob reaches the harness.** `--effort high` and `--effort low` and `--append-system-prompt` appear in the harness command line; caching off gives zero cache tokens; both caps end the trial with the cap's own stop reason. Pass.
- **Caps record their cost.** The turn-capped and spend-capped trials are scored by the hidden tests (both failed, having done almost nothing) and keep their cost. The spend cap of $0.005 was overshot by one request, to $0.016: well inside the in-flight allowance the ledger reserves for Haiku ($0.045). Pass.
- **Re-priced cost equals reported cost on all seven trials,** for Haiku 4.5 and Sonnet 5 as well as Opus 5 (spike 0001). The price table holds for the models the benchmark uses.
- **Cost per trial:** Haiku at most $0.053 (gate $0.06), Sonnet at most $0.087 (gate $0.12). Pass.
- **Ledger against console:** not reconciled; the provider consoles were not read again after the start.

Observations:

- **Low effort wrote 0.30× the output of high effort** on Sonnet 5 (526 against 1,725 tokens), in line with Opus 5 in spike 0001 (0.36×) and the pre-screen (about 0.35–0.4×).
- **Cache warmth again moved cost more than effort did.** `s5-low` cost more than `s5-high` because it ran second and paid a 28k-token cache write for its different prompt prefix. One trial per arm says nothing about cost; the headline uses a warm-up batch.
- **First real false-success flag.** In `s5-low` the agent wrote "All tests pass." after running only an ad-hoc `python -c` check, never the test file. The verifier's flag is correct by its definition (a "tests pass" claim with no test-runner run after the last edit). The code happened to be right: the hidden tests passed. So the flag means "unverified claim", not "wrong code"; the report wording should say so.

## Step 2: the first real release check, 2026-10-19

`canary watch --run -c examples/demo-suite --max-batches 2 --max-usd 1.00`. The watcher found Claude Code 2.1.303 on npm's `latest` tag, newer than the pinned 2.1.283, and compared the two on Haiku 4.5 and the three demo tasks, everything else held fixed. **Spend: $0.41** (expected about $0.30, worst case $1.28).

- **The two-version path works.** Each batch ran as two Harbor jobs, one per Claude Code version, each with its own cached binary mounted (ADR-0006). The 2.1.303 binary was downloaded once, checked against its release manifest and recorded in the bundle.
- **Every trial proved which version ran:** all six 2.1.283 trials read 2.1.283 and all six 2.1.303 trials read 2.1.303, from the harness's own transcript.
- **Re-priced cost again equalled reported cost** on all 12 trials.
- **The watcher remembered the release.** A second `canary watch` reports "new release already tested" and spends nothing.

| Metric (batch 1, after the warm-up batch) | 2.1.303 / 2.1.283 | 95% interval |
|---|---|---|
| Pass rate | 6/6 and 6/6 | no discordant pairs |
| Cost | ×1.20 | 0.96–1.67 |
| Output tokens | ×1.24 | 0.89–1.93 |
| Agent time | ×1.37 | 1.21–1.60, flagged |

The newer release took longer on these tasks. Three easy tasks and one batch of pairs make the interval too narrow to trust (the report says so below 20 tasks), so this is a lead, not a finding. A release check on the benchmark suite would settle it.

## Step 3: do the March–April builds still run? 2026-10-19

One trial each of Claude Code builds published on the postmortem dates, on Haiku 4.5 and `parse-duration`, installed from the harness cache (downloaded once, checksum-verified). **Spend: $0.16** (expected $0.12, worst case $0.39).

| Build | Published | Result | Cost | Requests | Version proven from transcript |
|---|---|---|---|---|---|
| 2.1.66 | 4 March (effort default lowered) | pass | $0.049 | 3 | 2.1.66 |
| 2.1.85 | 26 March (thinking-cache bug) | pass | $0.068 | 3 | 2.1.85 |
| 2.1.112 | 16 April (verbosity prompt) | pass | $0.043 | 6 | 2.1.112 |

- **All three still install and run against today's API**, with today's model, and their cost (from each build's own bundled price table) matches the canary's re-pricing.
- This answers the precondition for the planned headline replay demo: the builds run. It does **not** show they reproduce the incident. That needs the incident's model (Opus 4.6), the subscription's effort defaults rather than an API key's, and a real budget; it stays out of v0.1.

**Total after steps 1–3: $0.93** of the $22.50 ledger limit.

## Step X1: Codex adapter spike (OpenAI pool), 2026-10-20

Codex CLI 0.163.0 on `gpt-6-luna`, the three demo tasks at reasoning effort high and then low, one trial at a time, each bounded by a 120-second agent timeout (`examples/codex-spike/`). The Codex CLI is baked into the task image at the pinned version, so Harbor's per-trial install (about 200 MB) is skipped. **Spend: $0.014** of OpenAI credit (reservation $0.90 per run).

- **6 of 6 passed.** Cost per trial $0.0017–0.0036, 20–40× cheaper than Claude Code on Sonnet 5.
- **Version proven from the transcript** (`session_meta.cli_version`) on every trial.
- **Tokens and cost read, and re-priced cost equals reported cost**, so the OpenAI rows of the price table and Codex's cache-write field are right.
- **Low effort used fewer requests** (3–4 against 4–6) and 0.55× the output.
- **Codex runs in "code mode":** every action is one `exec` tool call holding a JavaScript snippet (`await tools.exec_command({cmd: …})`, patches as `*** Begin Patch` text). The verifier could not see edits or test runs inside it; it now reads them (verifier rules v2), tested against this real transcript.

## Step 4: price check on the 18 benchmark tasks, 2026-10-20

`s5-high-calibrate` (Sonnet 5, effort high, $0.40 cap) once on each selected task. **Spend: $2.80** (expected about $1.80; reserved $8.82). These trials never enter a test.

- **Baseline pass rate 12 of 18 (67%)**, the same as the pre-screen's high-effort arm (66%). The pre-screen's difficulty estimate transfers to the real harness.
- **Cost per trial: mean $0.155, median $0.137, highest $0.350.** That is twice the plan's $0.075 planning price: these tasks take more turns than the demo tasks (agent time mean 126 s, at most 278 s). No trial reached the cap.
- **The gate after step 4 fails as written.** At these prices a batch of 18 pairs costs about $4.50, and with caps of $0.25 the ledger can hold only 2 batches. So the headline design is revised below, before it runs.

**Total after step 4: Anthropic $3.72 of $22.50; OpenAI $0.01 of $9.00.**

## Step 5: the headline, 2026-10-20/21

`canary compare s5-high s5-low -c examples/benchmark-suite`: Claude Code 2.1.283 on Sonnet 5, reasoning effort high against low, the 10 tasks selected after step 4, at most 5 batches, futility look after batch 3. **Spend: $10.82** (expected about $8.80; the ledger held $7.80 per batch).

| Batch | Pairs | Discordant | Regressed / improved | E (threshold 20) |
|---|---|---|---|---|
| 0 | 10 | 3 | 2 / 1 | 1.13 |
| 1 | 20 | 5 | 3 / 2 | 0.99 |
| 2 | 30 | 9 | 7 / 2 | 2.95 |
| 3 | 40 | 13 | 10 / 3 | 4.57 |
| 4 | 50 | 17 | 13 / 4 | 7.15 |

**Verdict: not flagged.** The run reached its batch cap with E = 7.15, an anytime-valid p ≤ 0.14. The futility look after batch 3 let it continue (net 5 regressions, above the 4 required).

- **Pass rate: 32/50 (64%) at high effort against 23/50 (46%) at low**, a drop of 18 points. Discordant pairs went 13 to 4 against low effort.
- **A one-look test on the same trials would have flagged it.** The run reached its pre-registered cap, so the fixed-sample McNemar test is valid here: 13 of 17 discordant pairs, exact one-sided p = 0.025 (two-sided 0.049). This is the price of being allowed to look after every batch: the sequential test needs more evidence for the same error guarantee. It is also what a fixed-sample tool would have reported.
- **Transfer from the pre-screen was about 0.6:** the pre-screen predicted a drop of about 31 points on these tasks (after shrinkage); the real harness showed 18.
- **Cost and latency, low against high** (cluster bootstrap over 10 tasks, warm-up batch excluded; 10 tasks is fewer than the 20 at which these intervals are trustworthy):

  | Metric | Low / high | 95% interval |
  |---|---|---|
  | Cost | ×0.62 | 0.56–0.68 |
  | Output tokens | ×0.42 | 0.37–0.46 |
  | Agent time | ×0.64 | 0.51–0.76 |
  | Cache reads | ×0.84 | 0.71–0.99 |

- **Claims:** low effort said its tests pass in 45 of 50 trials, high effort in 27. None was a false success by the verifier's rule: every claim had a passing test run after the last edit. But low effort passed the hidden tests only 23 times, so at least 22 of its claims rested on the visible test alone, which the hidden ones go beyond.
- **No cap hits, no infrastructure errors, no dropped pairs.** Mean cost $0.132 per high-effort trial and $0.084 per low-effort one; the dearest trial was $0.249 under a $0.30 cap.

**Total after step 5: Anthropic $14.55 of $22.50; OpenAI $0.01 of $9.00.**

## Step 7: one extra batch of the headline, 2026-10-21

The plan's leftover rule (fixed before any spend): if the headline ends inconclusive at its batch cap with $15.00 or less spent, it gets one more batch. It ended at $14.55. `canary compare … --continue-from 20261020T174900Z-compare-98c8b5 --max-batches 1` continued the same e-process. **Spend: $2.18.**

**A departure from the plan:** the plan ordered step 6 (the caching check) before this step, and the $15.00 rule was meant to be read after it. This batch ran first. In the planned order, the ledger would have shown $16.30 and this batch would not have run. The verdict is the same either way: not flagged at 5 batches or at 6.

| Batch | Pairs | Discordant | Regressed / improved | E (threshold 20) |
|---|---|---|---|---|
| 5 | 60 | 21 | 16 / 5 | 11.31 |

**Final verdict: not flagged.** E = 11.3, anytime-valid p ≤ 0.088, after 6 batches and $13.00 in total for the headline.

- **Pass rate over 6 batches: 38/60 (63%) at high effort, 27/60 (45%) at low.**
- **Continuing was valid for the e-process** (it is a test supermartingale, so extending after a look keeps the 5% guarantee). It is **not** valid for a fixed-sample test: the McNemar figure that may be reported is the one at the pre-registered 5-batch cap (p = 0.025 one-sided), not one on all 6 batches.
- Cost and latency ratios barely moved: cost ×0.62 (0.57–0.67), output ×0.42 (0.36–0.46), agent time ×0.65 (0.54–0.75).

**What the headline can honestly say:** on 10 tasks and 120 trials, the canary's anytime-valid test did not flag a reasoning-effort cut on Claude Code with Sonnet 5 (E = 11.3 against 20), although pass rate fell 18 points and a one-look test at the pre-registered sample would have flagged it. Cost, tokens and latency fell clearly. At the observed rates, about 4 more batches (10 in all, about $22) would flag it 80% of the time (simulated); that does not fit this budget.

**Total after step 7: Anthropic $16.73 of $22.50.**

## Step 6: the caching-off cost check, 2026-10-21

`canary compare h45 h45-no-cache -c examples/benchmark-suite/cache-check.toml`: Claude Code 2.1.283 on Haiku 4.5, the 6 cheapest benchmark tasks, one batch; the candidate sets `DISABLE_PROMPT_CACHING=1`, a stand-in for the postmortem's thinking-block caching bug. **Spend: $1.75** (expected $1.30; caps $0.20 and $0.50 so that neither arm's cost was cut off; no cap was hit).

| Metric | Caching off / on | 95% interval | |
|---|---|---|---|
| Cost | ×2.63 | 1.75–4.10 | **flagged** |
| Cache reads and writes | ×0 | — | the knob took effect |
| Input tokens | ×0.62 | 0.41–1.00 | |
| Output tokens | ×0.85 | 0.56–1.47 | |
| Agent time | ×0.73 | 0.51–1.09 | |

- **The canary flagged the caching regression on cost after one batch of 6 tasks.** Every trial with caching off paid full input price on every request: $0.16–0.32 per trial against $0.03–0.14 with caching on.
- **Pass rate carried no information here, as expected for a cost regression:** Haiku 4.5 solved 0 of 6 and 1 of 6 of these tasks, which were tuned for Sonnet 5.
- **Six tasks make the interval too narrow to trust** in its exact bounds (the report warns below 20 tasks); the direction and the size of the effect are not in doubt.

**Total after step 6: Anthropic $18.48 of $22.50.** The Anthropic part of the plan is complete, within the campaign's $20 target.

## Step C1: Codex headroom check (OpenAI pool), 2026-10-21

Codex 0.163.0 on `gpt-6-luna`, reasoning effort high against low, all 32 candidate tasks, 2 attempts each, one batch (`examples/benchmark-suite-codex/prescreen.toml`). Calibration only: these trials choose Codex tasks and never enter a test. **Spend: $0.48** (expected about $0.65; reserved $6.40 at $0.05 per trial).

- **Codex solves almost everything at either effort:** 63/64 (98%) at high, 60/64 (94%) at low. The discordant pairs went 4 to 1 against low effort; E = 1.9.
- **The suite has no headroom for this stack.** The tasks were tuned against Sonnet 5 in Claude Code. `gpt-6-luna` in Codex passed all five tasks that no Sonnet 5 attempt ever passed (`human-bytes`, `log-window-count`, `monthly-recurrence`, `pagination-cursor`, `range-list`). That also answers a fairness worry about those five: a model can solve them as written.
- **Low effort costs much less for almost the same result:** cost ×0.58 (0.54–0.63), output ×0.37 (0.33–0.42), agent time ×0.64 (0.60–0.69). At $0.0028 a trial, low effort is the better buy on these tasks.
- **The verifier read Codex's code-mode transcripts on real data:** 54 "tests pass" claims, 2 flagged as false success (1 per arm).
- **Gate:** low effort shows no clear drop, so the planned replicated Codex comparison (C2) is not run on this suite. Nothing more is spent on it.

**Total after step C1: OpenAI $0.59 of $9.00.**

## Probe: Codex at reasoning effort "none", 2026-10-21

`canary run codex-none -c examples/benchmark-suite-codex`: the lowest effort Codex accepts, once on each of the 18 benchmark tasks. **Spend: $0.055.**

- **11 of 18 passed (61%)**, against 18 of 18 at high effort in step C0: a gap of about 39 points, large enough to measure a detection rate cheaply.
- **The 300-second agent timeout was not enforced.** Two trials ran 23 and 39 minutes (`dependency-order`, `env-file-parser`). Harbor received `override_timeout_sec = 300` (it is in the trial config) and its agent phase waits with `asyncio.wait_for(…, timeout=300)`, yet no `AgentTimeoutError` was raised. In the 39-minute trial, 38 minutes passed between two model requests with no tool running: the model call itself stalled (likely Codex retrying a stalled stream on this machine's slow link). Cost stayed small ($0.007), because waiting spends no tokens.
- **Consequence for the guardrails:** for a harness with no dollar cap, the agent timeout was meant to be the per-trial bound (ADR-0009). In Harbor 0.23.0 with Codex it is not reliable. The remaining bounds are the canary's batch watchdog (`[runner] batch_timeout_sec`, 4 hours by default), which kills the Harbor process, and the ledger, which keeps a killed batch reserved at its worst case. The roadmap records it; the root cause in Harbor is not established.

## Codex replicated detection benchmark, 2026-10-21

The pre-registered protocol (plan, "Codex replicated benchmark"; config `examples/benchmark-suite-codex/replicate.toml`, committed before the first run). Two streams of runs in parallel, 03:00–05:05 UTC. **Spend: $2.40 OpenAI** (expected about $3.70; worst case about $6.50). All seven runs are counted; none was repeated or dropped.

| Run | Decision | Batches | Regressed / improved | E | Passed (high against candidate) | Cost |
|---|---|---|---|---|---|---|
| Detection 1 | regression | 2 | 14 / 0 | 128 | 36/36 against 22/36 | $0.28 |
| Detection 2 | regression | 2 | 12 / 1 | 29.6 | 34/36 against 23/36 | $0.29 |
| Detection 3 | regression | 1 | 10 / 0 | 26.5 | 18/18 against 8/18 | $0.16 |
| Detection 4 | regression | 2 | 14 / 0 | 128 | 36/36 against 22/36 | $0.29 |
| Detection 5 | regression | 2 | 14 / 0 | 128 | 35/36 against 21/36 | $0.30 |
| Identical arms 1 | inconclusive (futility) | 3 | 1 / 2 | 0.6 | 52/54 against 53/54 | $0.55 |
| Identical arms 2 | inconclusive (futility) | 3 | 2 / 0 | 1.7 | 54/54 against 51/53 | $0.54 |

- **Detection: 5 of 5**, median 72 trials and $0.29 to flag (95% interval for the rate: 48%–100%). The three runs at E = 128 each had 14 regressed pairs and none improved.
- **False alarms: 0 of 2.** Cost ratios ×0.96 and ×1.02, neither flagged.
- **Effort none cost ×0.60 to ×0.66 of high.**
- **One infrastructure error** (a `VerifierTimeoutError` on identical-arms run 2), left out of the pairs.
- **A verifier fault, found and fixed:** Codex's tool output arrives as the text of a Python list with escaped line breaks, so the pytest summary never matched and every Codex claim read "unverifiable". Rules v3 decode it (ADR-0007). Re-checked on all campaign transcripts: 314 Codex claims moved to supported, none to false success, and no Claude Code verdict changed. The export now commits each run's re-checked verdicts (`claims.jsonl`).
- **Claims under rules v3:** effort none claimed "tests pass" in 146 of 162 trials, and the hidden tests then failed in 61 of them; high effort claimed it in 82 of 270, with 2 failures. Six claims were flagged as not backed by a test run after the last edit. Hand-checked: all six are right by the rule. Three of the late edits changed behaviour (two logic changes, one error message), three were cosmetic (moved imports, reworded docstrings); the hidden tests passed in all six.
