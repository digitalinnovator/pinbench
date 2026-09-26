# Roadmap

The v0.1 scope comes from the project brief. Anything outside it is parked under "Later" until v0.1 ships with its benchmark.

## v0.1: status as of 2026-09-27

| Item | Status |
|---|---|
| Git-native suite format (Harbor task format + `canary.toml`) | Done |
| Version-pinned pins: harness version, model, options, env, config files, with fingerprints | Done; config files are fingerprinted, but not yet delivered into the sandbox |
| Execution through Harbor (CLI, isolated hash-locked env, one job per batch) | Done; oracle/nop and Claude Code verified in Docker; harness binary cache (ADR-0006) |
| Claude Code adapter verified end to end with tokens, cost and transcript | Done: spike 0001, 3/3 on the demo suite, plus a first real A/B comparison |
| Codex and OpenCode pins verified end to end | Not started. Harbor has the adapters; needs a spike like 0001 for each |
| Sequential pass-rate test (paired mixture e-process) | Done (ADR-0003) |
| Bootstrap CIs on cost, tokens and latency | Done; cluster bootstrap over tasks |
| Budget caps (dollar and batch caps; per-trial harness caps through options) | Done |
| Immutable run bundles and SQLite index | Done (ADR-0004) |
| Static HTML report with per-task trace drill-down (ATIF) | Done; transcript view untested on real harness output |
| Cost normalisation from tokens with a pinned price table | ADR-0005 proposed; must land before any published cost number |
| Triggers: cron and new-release detection (npm dist-tags) | Not started |
| Alerts: Slack webhook and GitHub issue | Not started |
| Verifier-lite "false success" scorer on ATIF transcripts | Not started. Claude Code has no numeric exit code, and agents pipe test output (`pytest … \| tail`), so the rule must match test-runner *output* after the last edit (spike 0001) |
| "Canary in CI" scheduled GitHub Actions example | Not started |
| Regression-injection benchmark (detection power against runs and dollars) | Designed (injection pins in `examples/demo-suite`); needs a harder suite and a budget |

## Benchmark prerequisites

- **A suite with headroom.** The three demo tasks are likely to pass at 100% on a frontier model, which yields no discordant pairs and no signal. Candidates: a Terminal-Bench 2 subset through Harbor's registry, or 20–30 private-style tasks with measured baseline pass rates between 30% and 80%.
- **Power simulation before spending.** Use `SimulatedRunner` to estimate runs and dollars to detection for plausible effect sizes. Publish the simulation next to the measured numbers.
- **Comparison tests.** Wald SPRT and a fixed-N McNemar test on the same trial data, to justify ADR-0003 with numbers.
- **Old-build replay.** Check whether Claude Code 2.1.66–2.1.112 builds (March–April 2026) still install and behave consistently against today's API. 2.1.88 is unpublished. Packaging changed at 2.1.113.

## Known limitations to address

- **Prompt-cache warmth may bias cost comparisons** between arms when one configuration ran recently (spike 0001, section 4). Test it, then add a warm-up batch or cache-aware cost accounting.
- **Per-arm harness mounts.** The harness cache covers jobs whose Claude Code pins share a version. Comparing two versions still installs inside each sandbox (ADR-0006).

- **Few tasks make the bootstrap intervals too narrow.** Percentile intervals over fewer than about 20 tasks cover less often than they claim. Consider BCa or a t-based cluster interval, and warn in the report below a task threshold.
- **The bootstrap intervals are not anytime-valid.** A confidence-sequence replacement would allow peeking at cost as safely as at pass rate.
- **Pass/fail only.** Graded rewards need a different sequential test.
- **Intel-Mac wheel availability.** Upstreams are dropping `macosx_x86_64` wheels (cryptography ≥ 49, litellm 1.93.0). The Harbor env constrains those per platform. Watch for more.

## Later (post-v0.1, parked)

- "History mode": test a candidate against stored baseline runs for cheap daily monitoring, accepting drift risk explicitly.
- LLM-judge scoring with caching and small-to-large cascades (v0.2 per the brief).
- A full claim extractor for the verifier (v0.2).
- Pre-built harness images, so the sandbox needs no npm or installer egress at runtime.
- OpenTelemetry spans per batch and trial; ingesting harness OTel (Claude Code and Codex emit token and cost events).
- Retention and compression for run bundles.
- More runners behind the `Runner` protocol (Margin Eval as an external process, Inspect).
- Bisection across harness versions once a regression is flagged (config-drift-checker already does this for configs).
- A monthly harness efficiency index. Publish it as a time series; one-off harness comparisons are no longer novel (see the competitive re-check).
