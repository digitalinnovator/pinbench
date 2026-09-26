# C4 level 2: containers

v0.1 ships as one Python process (the `canary` CLI) plus the separately locked Harbor tool environment. The boxes inside the canary are modules, not services. They are drawn separately because each has its own contract and its own ADR. Items marked *planned* are in the v0.1 scope but are not built yet.

```mermaid
C4Container
    title Containers: Agent Canary (v0.1)

    Person(eng, "Platform / DevEx engineer")
    System_Ext(ci, "CI scheduler", "GitHub Actions")
    System_Ext(suite, "Task suite repo", "Harbor tasks + canary.toml")

    System_Boundary(c, "Agent Canary") {
        Container(cli, "CLI", "Python, Typer", "validate, run, compare, report, verify, index")
        Container(orch, "Compare orchestrator", "Python", "Batch loop: run both arms, update statistics, check budget, decide to stop")
        Container(stats, "Statistics engine", "NumPy, SciPy", "Mixture e-process on discordant pairs; cluster bootstrap on cost and latency (ADR-0003)")
        Container(runner, "Runner adapter", "Python", "Runner protocol; HarborRunner writes JobConfig YAML, runs harbor, parses result.json; SimulatedRunner for tests and power analysis")
        Container(verifier, "Verifier-lite (planned)", "Python", "Flags false success from ATIF transcripts")
        Container(trigger, "Release watcher (planned)", "Python", "Detects new harness versions")
        Container(alert, "Alerter (planned)", "Python", "Slack and GitHub Issues")
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
    Rel(trigger, orch, "Starts compare (planned)")
    Rel(orch, alert, "On regression (planned)")
    Rel(verifier, bundles, "Scores transcripts (planned)")

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
        float cost_usd
        float agent_seconds
        string installed_version
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
