# Agent Canary (working name)

**Know within a day whether Claude Code, Codex or OpenCode got worse, or more expensive, on *your* tasks.**

Agent Canary re-runs your own task suite against pinned versions of a coding-agent harness and model. It stops as soon as a regression in pass rate is statistically clear, and reports cost, token and latency changes with confidence intervals. It composes [Harbor](https://github.com/harbor-framework/harbor) for sandboxed execution and adds the missing layer on top: version pinning, sequential statistics, budgets and immutable evidence.

> **Status: pre-alpha, local development only.** The vertical slice works end to end: suite → paired runs → statistics → false-success check → sealed bundle → index → report. It has been verified against real Harbor sandboxes with Claude Code 2.1.283 ([spike 0001](docs/spikes/0001-harbor-claude-code.md)). No benchmark numbers are published yet. See the [roadmap](docs/roadmap.md).

<!-- Demo GIF goes here once the Claude Code spike has run (docs/spikes/0001-harbor-claude-code.md). -->

## Why

Anthropic's [2026-04-23 postmortem](https://www.anthropic.com/engineering/april-23-postmortem) traced weeks of Claude Code quality complaints to three **harness-layer** changes: a lower default reasoning effort, a thinking-block caching bug, and a verbosity system-prompt change. It stated that the API and model weights were unaffected. Trackers that watch only models miss that class of regression. Public trackers run their tasks, not yours. Vendors are poorly placed to referee their own releases.

## Headline benchmark

*Not yet published.* A [power simulation](benchmarks/results/power-simulation.md) (simulated, not measured) sizes it. The planned regression-injection benchmark injects the three postmortem failure types into a pinned Claude Code (`examples/demo-suite/canary.toml` has the injection pins). It then reports how many runs and dollars it takes to flag each regression at 95% confidence. Every number here will come from a committed benchmark script.

## Quickstart

From a checkout, with [uv](https://docs.astral.sh/uv/) installed:

```bash
make dev                                                        # canary env + hash-locked Harbor env
uv run canary compare stable regressed -c examples/simulated    # simulated: no Docker, no keys, no spend
open examples/simulated/.canary/reports/*.html                  # the report
```

Against real sandboxes (needs Docker; oracle and nop spend nothing):

```bash
uv run canary compare oracle nop -c examples/demo-suite
```

Against Claude Code (spends API credit; each trial is capped by `max_budget_usd`). Put your key in a gitignored `.env`:

```bash
uv run canary compare cc-baseline cc-low-effort -c examples/demo-suite --env-file .env
```

`canary compare` exits with 1 when it detects a regression, so it can gate a CI job.

Real runs are refused until you set a lifetime spending limit for the credit pool they draw on. Every batch reserves its worst case against that limit before it starts ([ADR-0009](docs/adr/0009-spending-guardrails.md)):

```bash
uv run canary ledger limit anthropic 20                                        # total this machine may ever spend
uv run canary compare cc-baseline cc-low-effort -c examples/demo-suite --dry-run   # what it could cost; spends nothing
uv run canary ledger status
```

On a schedule, test each new harness release once and alert on a regression:

```bash
uv run canary watch -c examples/demo-suite          # is there a newer release than the baseline pin? (no spend)
uv run canary watch --run -c examples/demo-suite    # compare baseline vs the same pin at the new version
```

[`examples/ci/agent-canary.yml`](examples/ci/agent-canary.yml) is a daily GitHub Actions job that does this. Alerts go to a Slack webhook and a GitHub issue ([ADR-0008](docs/adr/0008-triggers-and-alerts.md)); preview one with `canary alert <run> --dry-run`.

## How it works

```mermaid
flowchart LR
    S["Task suite<br/>(Harbor tasks + canary.toml)"] --> O
    subgraph canary["Agent Canary"]
        O["Compare loop"] -->|"one Harbor job per batch,<br/>both pins, every task"| R["Harbor runner"]
        R --> O
        O --> T["Paired e-process<br/>on pass rate"]
        O --> B["Cluster bootstrap<br/>on cost, tokens, latency"]
        O -->|"stop: significant,<br/>budget or batch cap"| U["Sealed run bundle<br/>(SHA256SUMS, read-only)"]
        U --> I[("SQLite index")]
        U --> H["Static HTML report"]
    end
    R -->|"harbor run -c job.yaml"| X["Docker / cloud sandboxes<br/>pinned harness version"]
```

- **Pins are cells of a version matrix.** A pin is harness × exact version × model × options × env × config files, identified by a fingerprint. Compare two pins that differ in one dimension and a regression is attributed to that dimension.
- **Paired and concurrent.** Each batch runs every task on both pins in the same Harbor job. Pairing removes task-difficulty variance. Running both arms together controls for API drift during the day.
- **Stops early, safely.** The pass-rate test is a mixture e-process on discordant pairs. Checking it after every batch does not inflate the false-alarm rate ([ADR-0003](docs/adr/0003-sequential-paired-statistics.md)). With the defaults (α = 0.05, mixture bound 0.8) it needs at least 10 discordant pairs to flag anything. The mixture bound was chosen by a [power simulation](benchmarks/results/power-simulation.md), which also shows that re-checking a fixed-sample test after every batch gives 14–19% false alarms instead of 5%.
- **Catches false success.** A rule-based verifier reads each transcript and checks every "tests pass" claim against the agent's own test-runner output after its last edit. No model is involved ([ADR-0007](docs/adr/0007-verifier-lite.md)). `canary claims <run>` re-scores any stored run.
- **Cannot run up a bill.** A campaign ledger holds a lifetime limit per credit pool across all runs. A batch starts only if its worst case fits, unknown costs count at the cap, and a run stops when the account is empty or a batch yields nothing ([ADR-0009](docs/adr/0009-spending-guardrails.md)).
- **Evidence you can audit.** Every run is a bundle holding the manifest (task digests, pin fingerprints, Harbor version, settings), raw Harbor trial directories, normalised trials and the verdict. The bundle is checksummed and made read-only ([ADR-0004](docs/adr/0004-run-bundles-and-index.md)).

Architecture: [C4 context](docs/architecture/c4-context.md) · [C4 containers and data model](docs/architecture/c4-container.md) · [ADRs](docs/adr/).

## Configuration sketch

```toml
[suite]
name = "my-team"
tasks_dir = "tasks"            # Harbor task format: task.toml, instruction.md, environment/, tests/

[budget]
max_usd = 20.0                 # checked before each batch against the average batch cost so far
max_batches = 10
attempts_per_batch = 1

[pins.current]
harness = "claude-code"
version = "2.1.283"            # exact versions only; drift between pin and installed version fails the run
model = "anthropic/claude-opus-5"
options = { reasoning_effort = "high", max_budget_usd = "1.00" }

[pins.next]
harness = "claude-code"
version = "2.1.284"
model = "anthropic/claude-opus-5"
options = { reasoning_effort = "high", max_budget_usd = "1.00" }
```

## Limitations (read before trusting a number)

- The harness under test is the harness **as Harbor launches it**: headless print mode, permissions bypassed. That is right for regression detection, and it is not your interactive setup.
- Cost is **re-priced from token usage** with a dated price table in this repo, so a harness that changes its bundled prices does not look like a regression ([ADR-0005](docs/adr/0005-cost-normalisation.md)). The table covers Anthropic models at first-party API prices; anything else falls back to the harness's own estimate and the report says so.
- **Prompt-cache state moves cost.** A configuration's first trials pay a cache write that later ones do not. On small suites set `[stats] warmup_batches = 1`, and read a cost ratio together with `cache_write_tokens`.
- Cost and latency intervals are fixed-sample at the stopping time and are too narrow with fewer than about 20 tasks.
- The false-success check favours precision: it misses hedged or unusual claims, reads test-runner output and not exit codes, and is verified on Claude Code transcripts only.
- Tasks that always pass or always fail cost money and add no evidence. The report shows which tasks were discordant.

## Alternatives

A dated comparison, re-checked on 2026-09-27, is in [docs/research/2026-09-27-competitive-recheck.md](docs/research/2026-09-27-competitive-recheck.md). In short:

- **Harbor and Margin Eval** are runners. This project builds on Harbor rather than competing with it.
- **MarginLab** tracks a public SWE-Bench-Pro subset.
- **UiPath coder_eval** runs A/B experiments on your own tasks with fixed-sample statistics.
- **config-drift-checker** watches Claude Code releases against config-level evals.

No project found combines private suites, a harness-version matrix, sequential stopping, cost intervals and Apache-2.0 licensing. Re-verify before relying on this: the space moves weekly.

## Contributing

```bash
make dev && make check     # ruff, mypy --strict, pytest
make docker-test           # real Harbor trials with the zero-cost oracle and nop agents
```

Record significant decisions as ADRs in `docs/adr/`. Keep v0.1 narrow and park ideas in `docs/roadmap.md`.

## License

[Apache-2.0](LICENSE).
