# Roadmap

The v0.1 scope comes from the project brief. Anything outside it is parked under "Later" until v0.1 ships with its benchmark.

## v0.1: status as of 2026-09-30

| Item | Status |
|---|---|
| Git-native suite format (Harbor task format + `canary.toml`) | Done |
| Version-pinned pins: harness version, model, options, env, config files, with fingerprints | Done; config files are fingerprinted, but not yet delivered into the sandbox |
| Execution through Harbor (CLI, isolated hash-locked env, one job per batch) | Done; oracle/nop and Claude Code verified in Docker; harness binary cache (ADR-0006) |
| Claude Code adapter verified end to end with tokens, cost and transcript | Done: spike 0001, 3/3 on the demo suite, plus a first real A/B comparison |
| Codex and OpenCode pins verified end to end | Not started. Harbor has the adapters; needs a spike like 0001 for each |
| Sequential pass-rate test (paired mixture e-process) | Done (ADR-0003) |
| Bootstrap CIs on cost, tokens and latency | Done; cluster bootstrap over tasks |
| Budget caps (soft `max_usd` per run; hard lifetime ledger per credit pool; per-trial caps) | Done (ADR-0009); tested with fake runners only |
| Immutable run bundles and SQLite index | Done (ADR-0004) |
| Static HTML report with per-task trace drill-down (ATIF) | Done; transcript view untested on real harness output |
| Cost normalisation from tokens with a pinned price table | Done (ADR-0005 accepted): `cost_usd` re-priced per request from the transcript; reproduces the reported cost on all 15 real trials. Anthropic first-party prices only |
| Triggers: cron and new-release detection (npm dist-tags) | Done (ADR-0008): `canary watch [--run]`, scheduled by CI; each release tested once. Checked live against npm; `--run` exercised with the simulated runner only |
| Alerts: Slack webhook and GitHub issue | Done (ADR-0008): sent after sealing, de-duplicated issues, `canary alert --dry-run`. Tested against fake transports; nothing has been sent to a real channel |
| Verifier-lite "false success" scorer on ATIF transcripts | Done (ADR-0007): rule-based, matches test-runner *output* after the last edit; per-arm counts in the verdict, report and index; `canary claims` re-scores old bundles. Verified on Claude Code transcripts only |
| "Canary in CI" scheduled GitHub Actions example | Written (`examples/ci/agent-canary.yml`, SHA-pinned actions). Not yet run on GitHub |
| Regression-injection benchmark (detection power against runs and dollars) | Ready to run, awaiting the owner's go-ahead: 18 tasks selected by a free pre-screen ([prescreen.md](benchmark/prescreen.md)), guardrails built, plan fixed ([plan](benchmark/plan.md)) |

## Benchmark prerequisites

- **A suite with headroom.** The three demo tasks are likely to pass at 100% on a frontier model, which yields no discordant pairs and no signal. Candidates: a Terminal-Bench 2 subset through Harbor's registry, or 20–30 private-style tasks with measured baseline pass rates between 30% and 80%.
- **Power simulation before spending.** Use `SimulatedRunner` to estimate runs and dollars to detection for plausible effect sizes. Publish the simulation next to the measured numbers.
- **Comparison tests.** Wald SPRT and a fixed-N McNemar test on the same trial data, to justify ADR-0003 with numbers.
- **Old-build replay.** Check whether Claude Code 2.1.66–2.1.112 builds (March–April 2026) still install and behave consistently against today's API. 2.1.88 is unpublished. Packaging changed at 2.1.113.

## Known limitations to address

- **Spending guardrails are built but have never met a real harness.** A campaign ledger now bounds spend across runs (ADR-0009), after an audit showed `max_usd` was not a bound. Twenty-eight review findings were fixed and are covered by tests. Still unverified on a real run: that `--max-budget-usd` stops a trial as assumed, the size of the in-flight overshoot, and the exact text Claude Code prints for an empty account.
- **A per-trial dollar cap can act as a treatment.** A capped trial is scored on whatever it had finished, which is usually a failure. Use the same `max_budget_usd` and `max_turns` on both arms and count cap hits per arm.
- **`--effort` is ignored on Haiku 4.5.** Claude Code drops it silently, so an effort comparison on that model is an A/A run. `canary validate` warns about it.
- **Codex and OpenCode are not ready for the canary.** Neither has a per-trial dollar cap. Codex writes cache writes under a different key than the price table reads, and its current models use a code-mode tool the verifier misreads. OpenCode echoes the requested version, so its version proof is hollow. The harness cache covers neither.
- **`benchmarks/power_simulation.py` raises on an infeasible drop** (`brentq` bracket, small suites with a 40-point drop). Clamp the shift or report the cell as infeasible.

- **Prompt-cache warmth biases cost on small suites.** Confirmed from the spike's transcripts (spike 0001, section 4): a configuration's first trials pay a ~16k-token cache write. Cache reads and writes are now separate metrics and `[stats] warmup_batches` drops early batches from the cost comparison. Still open: the first `n_concurrent` trials after any five-minute gap are cold, and no real run has used the warm-up setting yet.
- **Two-version runs are untested against real Harbor.** Pins on different Claude Code versions now run as one concurrent Harbor job per version, each with its own cached binary (ADR-0006). That path is tested against a fake Harbor CLI only. The first real `canary watch --run` should be watched.

- **The price table covers Anthropic models only.** Add OpenAI prices, verified against the provider's page, with the Codex spike. Until then Codex trials compare on reported cost.
- **Few tasks make the bootstrap intervals too narrow.** Percentile intervals over fewer than about 20 tasks cover less often than they claim. Consider BCa or a t-based cluster interval, and warn in the report below a task threshold.
- **The bootstrap intervals are not anytime-valid.** A confidence-sequence replacement would allow peeking at cost as safely as at pass rate.
- **Pass/fail only.** Graded rewards need a different sequential test.
- **Intel-Mac wheel availability.** Upstreams are dropping `macosx_x86_64` wheels (cryptography ≥ 49, litellm 1.93.0). The Harbor env constrains those per platform. Watch for more.

## Later (post-v0.1, parked)

- "History mode": test a candidate against stored baseline runs for cheap daily monitoring, accepting drift risk explicitly.
- Ease the five benchmark tasks that no pre-screen attempt passed (`human-bytes`, `log-window-count`, `monthly-recurrence`, `pagination-cursor`, `range-list`); each fails on input-validation rules at both efforts ([prescreen.md](benchmark/prescreen.md)).
- Multi-step Harbor tasks (`[[steps]]`): refused for now, because each step gets a fresh spend cap and its cost is not read (ADR-0009).
- LLM-judge scoring with caching and small-to-large cascades (v0.2 per the brief).
- A false-success dataset: run `canary claims` over the benchmark's bundles and publish the rate per harness and effort level, with hand-labelled precision for the flags. No public dataset exists.
- A full claim extractor for the verifier (v0.2).
- Pre-built harness images, so the sandbox needs no npm or installer egress at runtime.
- OpenTelemetry spans per batch and trial; ingesting harness OTel (Claude Code and Codex emit token and cost events).
- Retention and compression for run bundles.
- More runners behind the `Runner` protocol (Margin Eval as an external process, Inspect).
- Bisection across harness versions once a regression is flagged (config-drift-checker already does this for configs).
- A monthly harness efficiency index. Publish it as a time series; one-off harness comparisons are no longer novel (see the competitive re-check).
