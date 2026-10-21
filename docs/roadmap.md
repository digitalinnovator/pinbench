# Roadmap

The v0.1 scope comes from the project brief. Anything outside it is parked under "Later" until v0.1 ships with its benchmark.

## v0.1: status as of 2026-10-21

| Item | Status |
|---|---|
| Git-native suite format (Harbor task format + `canary.toml`) | Done |
| Version-pinned pins: harness version, model, options, env, config files, with fingerprints | Done; config files are fingerprinted, but not yet delivered into the sandbox |
| Execution through Harbor (CLI, isolated hash-locked env, one job per batch; one job per Claude Code version) | Done; verified on real trials with oracle/nop, Claude Code and Codex |
| Claude Code adapter | Done: versions 2.1.66, 2.1.85, 2.1.112, 2.1.283 and 2.1.303 on Opus 5, Sonnet 5 and Haiku 4.5; version proven from the transcript on every trial |
| Codex adapter | Done: Codex 0.163.0 on `gpt-6-luna` through a baked image; version proof, re-priced cost, code-mode transcripts read by the verifier |
| OpenCode adapter | Not verified: its version proof would be hollow (Harbor echoes the requested version) and its cost comes from a runtime catalogue |
| Sequential pass-rate test (paired mixture e-process), with optional continuation (`--continue-from`) | Done (ADR-0003) |
| Bootstrap CIs on cost, tokens and latency | Done; cluster bootstrap over tasks |
| Budget caps (soft `max_usd` per run; hard lifetime ledger per credit pool; per-trial caps) | Done (ADR-0009); held on every real run of the October campaign |
| Immutable run bundles and SQLite index | Done (ADR-0004) |
| Static HTML report with per-task trace drill-down (ATIF) | Done; transcripts from real Claude Code and Codex trials render |
| Cost normalisation from tokens with a pinned price table | Done (ADR-0005): Anthropic and OpenAI prices; equals the harness-reported cost on every real trial |
| Triggers: cron and new-release detection (npm dist-tags) | Done (ADR-0008): a real `canary watch --run` tested Claude Code 2.1.303 against 2.1.283 |
| Alerts: Slack webhook and GitHub issue | Done (ADR-0008). Tested against fake transports; nothing has been sent to a real channel |
| Verifier-lite "false success" scorer on ATIF transcripts | Done (ADR-0007), rules v3: Claude Code and Codex transcripts; 6 Codex flags hand-checked, all correct by the rule |
| "Canary in CI" scheduled GitHub Actions example | Written (`examples/ci/agent-canary.yml`, SHA-pinned actions, persistent ledger). Not yet run on GitHub |
| Regression-injection benchmark | Done for v0.1 ([campaign log](benchmark/campaign-log.md), [report](../benchmarks/results/campaign-2026-10.md)): Claude Code headline, caching check, and a replicated Codex detection rate (5 of 5, 0 of 2 false alarms) |

## Before launch

- **A demo GIF** for the README (the launch shape asks for one): a `canary compare` run and its report.
- **The working name.** "canary" collides with a YC company and two repositories (competitive re-check).
- **Publishing the full run bundles** (about 70 MB of transcripts) as a release asset, so anyone can re-verify the committed evidence files against them. Needs the owner's decision.
- **Re-verify the competitive comparison** on the day of launch.

## Known limitations to address

- **Harbor 0.23.0 did not enforce the agent timeout for Codex.** Two Codex trials ran 23 and 39 minutes under a 300-second `override_timeout_sec` (campaign log, probe). For harnesses with no dollar cap the timeout was meant to bound each trial; until the cause is found, rely on `[runner] batch_timeout_sec` and the ledger, and report it upstream (owner's decision).
- **A pass-rate drop of 18 points on 10 tasks was not flagged within 6 batches** (campaign log, step 7). The anytime-valid test pays for its freedom to look after every batch with more evidence than a one-look test needs. A suite of 25–50 tasks, or several attempts per task per batch, would detect such drops at a cost a team can choose.
- **A per-trial dollar cap can act as a treatment.** A capped trial is scored on whatever it had finished, which is usually a failure. Use the same `max_budget_usd` and `max_turns` on both arms; the report counts cap hits per arm.
- **`--effort` is ignored on Haiku 4.5.** Claude Code drops it silently, so an effort comparison on that model is an A/A run. `canary validate` warns about it.
- **Prompt-cache warmth biases cost on small suites.** A configuration's first trials pay a cache write that later ones do not. Cache reads and writes are separate metrics and `[stats] warmup_batches` drops early batches from the cost comparison; the first trials after a five-minute gap are still cold.
- **A suite tuned for one model can be saturated for another.** The benchmark suite, tuned against Sonnet 5, gave Codex on `gpt-6-luna` 98% at high effort. Tune a suite per harness-and-model stack.
- **Codex: what remains.** A host-side binary cache like Claude Code's (the image bakes the CLI instead).
- **Few tasks make the bootstrap intervals too narrow.** Percentile intervals over fewer than about 20 tasks cover less often than they claim. Consider BCa or a t-based cluster interval, and warn in the report below a task threshold.
- **The bootstrap intervals are not anytime-valid.** A confidence-sequence replacement would allow peeking at cost as safely as at pass rate.
- **Pass/fail only.** Graded rewards need a different sequential test.
- **`benchmarks/power_simulation.py` raises on an infeasible drop** (`brentq` bracket, small suites with a 40-point drop). Clamp the shift or report the cell as infeasible.
- **Intel-Mac wheel availability.** Upstreams are dropping `macosx_x86_64` wheels (cryptography ≥ 49, litellm 1.93.0). The Harbor env constrains those per platform. Watch for more.

## Later (post-v0.1, parked)

- "History mode": test a candidate against stored baseline runs for cheap daily monitoring, accepting drift risk explicitly.
- Ease the five benchmark tasks that no Sonnet 5 pre-screen attempt passed (`human-bytes`, `log-window-count`, `monthly-recurrence`, `pagination-cursor`, `range-list`). Codex passes them, so they are solvable as written.
- Multi-step Harbor tasks (`[[steps]]`): refused for now, because each step gets a fresh spend cap and its cost is not read (ADR-0009).
- LLM-judge scoring with caching and small-to-large cascades (v0.2 per the brief).
- A false-success dataset: run `canary claims` over the benchmark's bundles and publish the rate per harness and effort level, with hand-labelled precision for the flags. No public dataset exists.
- A full claim extractor for the verifier (v0.2).
- OpenTelemetry spans per batch and trial; ingesting harness OTel (Claude Code and Codex emit token and cost events).
- Retention and compression for run bundles.
- More runners behind the `Runner` protocol (Margin Eval as an external process, Inspect).
- Bisection across harness versions once a regression is flagged (config-drift-checker already does this for configs).
- A monthly harness efficiency index, published as a time series. The campaign has its first row (dollars per solved task per stack).
- The March–April 2026 timeline replay: the old builds run, but reproducing the incident needs Opus 4.6, the subscription's effort defaults and a larger budget.
