# Benchmark campaign log

Every paid step of the [plan](plan.md), in order, with what it cost and what it showed. Spend is the canary's ledger figure (`canary ledger status`); it is reconciled against the provider console after each step.

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
- **Ledger against console:** pending the owner's check.

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
- This answers the precondition the project brief set for the headline replay demo: the builds run. It does **not** show they reproduce the incident. That needs the incident's model (Opus 4.6), the subscription's effort defaults rather than an API key's, and a real budget; it stays out of v0.1.

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
