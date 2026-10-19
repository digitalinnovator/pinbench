# C4 level 2: containers

v0.1 ships as one Python process (the `canary` CLI) plus the separately locked Harbor tool environment. The boxes inside the canary are modules, not services. They are drawn separately because each has its own contract and its own ADR.

```mermaid
C4Container
    title Containers: Agent Canary (v0.1)

    Person(eng, "Platform / DevEx engineer")
    System_Ext(ci, "CI scheduler", "GitHub Actions")
    System_Ext(suite, "Task suite repo", "Harbor tasks + canary.toml")

    System_Boundary(c, "Agent Canary") {
        Container(cli, "CLI", "Python, Typer", "validate, run, compare, watch, alert, ledger, report, claims, verify, index")
        Container(orch, "Compare orchestrator", "Python", "Batch loop: run both arms, update statistics, check budget, decide to stop")
        Container(stats, "Statistics engine", "NumPy, SciPy", "Mixture e-process on discordant pairs; cluster bootstrap on cost, tokens and latency (ADR-0003)")
        Container(ledger, "Campaign ledger", "Python, JSON lines", "Lifetime spending limit per credit pool; reserves each batch's worst case, then settles (ADR-0009)")
        Container(pricing, "Pricing", "Python, TOML", "Re-prices each trial from transcript token usage with a dated price table (ADR-0005)")
        Container(runner, "Runner adapter", "Python", "Runner protocol; HarborRunner writes JobConfig YAML, runs harbor, parses result.json; SimulatedRunner for tests and power analysis")
        Container(verifier, "Verifier-lite", "Python", "Checks 'tests pass' claims against test-runner output in ATIF transcripts (ADR-0007)")
        Container(trigger, "Release watcher", "Python", "Reads npm dist-tags; derives a candidate pin for a new harness version (ADR-0008)")
        Container(alert, "Alerter", "Python", "Slack webhook and GitHub issue, sent after the bundle is sealed (ADR-0008)")
        Container(report, "Report renderer", "Jinja2", "Static HTML with per-task drill-down")
        ContainerDb(bundles, "Run bundles", "Filesystem", "Immutable, checksummed system of record (ADR-0004)")
        ContainerDb(index, "Run index", "SQLite", "Derived, rebuildable query index")
    }

    System_Ext(harbor, "Harbor CLI", "Isolated uv environment, pinned 0.23.0 (ADR-0002)")

    Rel(eng, cli, "Runs")
    Rel(ci, cli, "Runs on schedule")
    Rel(cli, orch, "compare")
    Rel(orch, runner, "run_batch(pins, tasks)")
    Rel(runner, harbor, "subprocess: harbor run -c job.yaml")
    Rel(runner, suite, "Reads tasks")
    Rel(orch, stats, "Update and test")
    Rel(orch, bundles, "Writes and seals")
    Rel(orch, index, "Ingests")
    Rel(report, bundles, "Reads")
    Rel(ci, trigger, "canary watch --run, on a schedule")
    Rel(trigger, orch, "Starts compare for a new release")
    Rel(alert, bundles, "Reads verdict")
    Rel(runner, verifier, "Scores each transcript")
    Rel(runner, pricing, "Prices each transcript")
    Rel(orch, ledger, "Reserves before each batch, settles after")
    Rel(verifier, bundles, "Re-scores sealed transcripts (canary claims)")

    UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")
```

## Data model: the version matrix

```mermaid
erDiagram
    SUITE ||--o{ TASK : contains
    PIN ||--o{ TRIAL : "runs as"
    TASK ||--o{ TRIAL : "is attempted in"
    RUN ||--o{ TRIAL : records
    RUN }o--|| SUITE : "at commit"
    RUN ||--o| VERDICT : "compare runs"

    PIN {
        string name
        string harness "claude-code | codex | opencode"
        string version "exact harness CLI version"
        string model "exact model id"
        json options "effort, system-prompt additions, caps"
        string fingerprint "sha256 of canonical spec"
    }
    TASK {
        string name
        string digest "sha256 of task dir"
    }
    TRIAL {
        string trial_name
        int batch
        string status "pass | fail | error"
        float reward
        int input_tokens
        int cache_tokens
        int output_tokens
        int cache_write_tokens
        float cost_usd "re-priced from tokens (ADR-0005)"
        float reported_cost_usd "the harness's own estimate"
        float agent_seconds
        string installed_version
        string claim_check "no_claim | supported | false_success | unverifiable"
    }
    RUN {
        string run_id
        string kind "run | compare"
        string harbor_version
        string suite_commit
    }
    VERDICT {
        string decision "regression | improvement | inconclusive"
        float e_value
        float p_value
        string stop_reason
    }
```

A pin is one cell of the version matrix. Comparing two pins that differ in exactly one dimension, such as the harness version with the model held fixed, attributes a regression to that dimension. That is the harness-versus-model distinction model-only trackers cannot make.
