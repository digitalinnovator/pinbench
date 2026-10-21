# C4 level 1: system context

pinbench sits between a team's private task suite and the coding-agent harnesses the team depends on. It never hosts anything. It runs where the team runs it: a laptop, a CI runner, or a scheduled GitHub Actions workflow.

```mermaid
C4Context
    title System context: pinbench (v0.1)

    Person(eng, "Platform / DevEx engineer", "Owns the team's agent setup; decides whether to adopt a new harness or model version")

    System(pinbench, "pinbench", "Schedules paired runs of pinned harness versions on the team's own tasks, detects regressions in pass rate, cost and latency, keeps immutable run bundles")

    System_Ext(suite, "Private task suite", "Git repo of Harbor-format tasks plus pinbench.toml")
    System_Ext(harbor, "Harbor", "Apache-2.0 agent evaluation framework; runs trials in sandboxes")
    System_Ext(sandbox, "Sandbox provider", "Local Docker, or Daytona / Modal / E2B via Harbor")
    System_Ext(harness, "Harness distributions", "npm registry and release feeds for Claude Code, Codex, OpenCode")
    System_Ext(models, "Model APIs", "Anthropic, OpenAI and others; called by the harness, never by pinbench")
    System_Ext(ci, "CI scheduler", "GitHub Actions cron and release-triggered workflows")
    System_Ext(alerts, "Alert sinks", "Slack webhook, GitHub Issues")

    Rel(eng, pinbench, "Defines pins and budgets; reads verdicts and reports")
    Rel(ci, pinbench, "Triggers on cron / new harness release")
    Rel(pinbench, suite, "Reads tasks, digests them")
    Rel(pinbench, harbor, "Generates job configs; runs harbor CLI; parses trial output")
    Rel(harbor, sandbox, "Builds task images, runs trials")
    Rel(sandbox, harness, "Installs the pinned harness version")
    Rel(sandbox, models, "Harness calls model")
    Rel(pinbench, harness, "Polls npm for new versions")
    Rel(pinbench, alerts, "Posts regressions")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Trust and cost boundaries

- **Secrets.** Model API keys pass from the operator's environment to Harbor to the sandbox. pinbench records their names, never their values (ADR-0004).
- **Spend.** All token spend happens inside the sandbox, through the harness. pinbench controls spend by deciding whether to start another batch (ADR-0003), and by passing per-trial caps such as Claude Code's `max_budget_usd`.
- **Network.** The sandbox needs egress to the npm registry or Anthropic's installer, and to the model API. pinbench itself makes only small HTTPS requests: npm release checks and alerts.
