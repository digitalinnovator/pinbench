# Roadmap

The v0.1 scope was fixed at the start of the project. Anything outside it is parked under "Later" until v0.1 ships with its benchmark.

## v0.1: status as of 2026-10-21

| Item | Status |
|---|---|
| Git-native suite format (Harbor task format + `pinbench.toml`) | Done |
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
| Cost normalisation from tokens with a pinned price table | Done (ADR-0005): Anthropic and OpenAI prices; matches the harness-reported cost on 879 of 882 committed trials |
| Triggers: cron and new-release detection (npm dist-tags) | Done (ADR-0008): a real `pinbench watch --run` tested Claude Code 2.1.303 against 2.1.283 |
| Alerts: Slack webhook and GitHub issue | Done (ADR-0008). Tested against fake transports; nothing has been sent to a real channel |
| Verifier-lite "false success" scorer on ATIF transcripts | Done (ADR-0007), rules v3: Claude Code and Codex transcripts; 6 Codex flags hand-checked, all correct by the rule |
| "pinbench in CI" scheduled GitHub Actions example | Written (`examples/ci/pinbench.yml`, SHA-pinned actions, persistent ledger). Not yet run on GitHub |
| Regression-injection benchmark | Done for v0.1 ([campaign log](benchmark/campaign-log.md), [report](../benchmarks/results/campaign-2026-10.md)): Claude Code headline, caching check, and a replicated Codex detection rate (5 of 5, 0 of 2 false alarms) |

## Before launch

- **The demo GIF** is a recording of the simulated compare. A recording of a real Claude Code run and its HTML report would be stronger.
- **The name is decided: `pinbench`** ([ADR-0010](adr/0010-name-pinbench.md)), despite an unrelated PinBench organisation and domain. Check the trademark register before wider promotion.
- **Publishing the full run bundles** (about 70 MB of transcripts) as a release asset, so anyone can re-verify the committed evidence files against them. Not done: each Claude Code trial also holds harness session files with account identifiers (`agent/sessions/`), which must be left out first.
- **Re-verify the competitive comparison** on the day of launch.
- **The verbosity regression** (one of the postmortem's three changes) has had only a smoke trial; measuring it on Haiku 4.5 would cost about $1–2.

## Known limitations to address

- **Harbor 0.23.0 did not enforce the agent timeout for Codex.** Two Codex trials ran 23 and 39 minutes under a 300-second `override_timeout_sec` (campaign log, probe). For harnesses with no dollar cap the timeout was meant to bound each trial; until the cause is found, rely on `[runner] batch_timeout_sec` and the ledger, and report it upstream.
- **Three re-priced costs differ from the harness's own figure.** Three Sonnet 5 trials of the headline run re-priced 4–14% below the cost Claude Code reported (campaign report, re-pricing check). The cause is not yet known.
- **A pass-rate drop of 18 points on 10 tasks was not flagged within 6 batches** (campaign log, step 7). The anytime-valid test pays for its freedom to look after every batch with more evidence than a one-look test needs. A suite of 25–50 tasks, or several attempts per task per batch, would detect such drops at a cost a team can choose.
- **A per-trial dollar cap can act as a treatment.** A capped trial is scored on whatever it had finished, which is usually a failure. Use the same `max_budget_usd` and `max_turns` on both arms; the report counts cap hits per arm.
- **`--effort` is ignored on Haiku 4.5.** Claude Code drops it silently, so an effort comparison on that model is an A/A run. `pinbench validate` warns about it.
- **Prompt-cache warmth biases cost on small suites.** A configuration's first trials pay a cache write that later ones do not. Cache reads and writes are separate metrics and `[stats] warmup_batches` drops early batches from the cost comparison; the first trials after a five-minute gap are still cold.
- **A suite tuned for one model can be saturated for another.** The benchmark suite, tuned against Sonnet 5, gave Codex on `gpt-6-luna` 98% at high effort. Tune a suite per harness-and-model stack.
- **Codex: what remains.** A host-side binary cache like Claude Code's (the image bakes the CLI instead).
- **Few tasks make the bootstrap intervals too narrow.** Percentile intervals over fewer than about 20 tasks cover less often than they claim. Consider BCa or a t-based cluster interval, and warn in the report below a task threshold.
- **The bootstrap intervals are not anytime-valid.** A confidence-sequence replacement would allow peeking at cost as safely as at pass rate.
- **Pass/fail only.** Graded rewards need a different sequential test.
- **`benchmarks/power_simulation.py` raises on an infeasible drop** (`brentq` bracket, small suites with a 40-point drop). Clamp the shift or report the cell as infeasible.
- **Intel-Mac wheel availability.** Upstreams are dropping `macosx_x86_64` wheels (cryptography ≥ 49, litellm 1.93.0). The Harbor env constrains those per platform. Watch for more. On Intel Macs this holds `cryptography` at 48.0.1 (other platforms get 50.0.1). 48.0.1 has three advisories, fixed in 49 and 50, neither of which publishes Intel-Mac wheels: two in its X.509 path verifier (one high, one medium) and one high in PKCS#7 decryption. Accepted on 2026-10-21, because no package in the Harbor environment calls either API (searched that day). Revisit if a dependency starts to. Security fixes newer than the dependency date cutoff are admitted one package at a time, with a provenance check (`exclude-newer-package` in `tools/harbor/pyproject.toml`: `certifi` and `aiohttp` on 2026-10-21).

## Later (post-v0.1, parked)

- "History mode": test a candidate against stored baseline runs for cheap daily monitoring, accepting drift risk explicitly.
- Ease the five benchmark tasks that no Sonnet 5 pre-screen attempt passed (`human-bytes`, `log-window-count`, `monthly-recurrence`, `pagination-cursor`, `range-list`). Codex passes them, so they are solvable as written.
- Multi-step Harbor tasks (`[[steps]]`): refused for now, because each step gets a fresh spend cap and its cost is not read (ADR-0009).
- LLM-judge scoring with caching and small-to-large cascades (planned for v0.2).
- A false-success dataset: run `pinbench claims` over the benchmark's bundles and publish the rate per harness and effort level, with hand-labelled precision for the flags. No public dataset exists.
- A full claim extractor for the verifier (v0.2).
- OpenTelemetry spans per batch and trial; ingesting harness OTel (Claude Code and Codex emit token and cost events).
- Retention and compression for run bundles.
- More runners behind the `Runner` protocol (Margin Eval as an external process, Inspect).
- Bisection across harness versions once a regression is flagged (config-drift-checker already does this for configs).
- A monthly harness efficiency index, published as a time series. The campaign has its first row (dollars per solved task per stack).
- The March–April 2026 timeline replay: the old builds run, but reproducing the incident needs Opus 4.6, the subscription's effort defaults and a larger budget.
