# Competitive re-check: private-suite harness monitors (2026-09-27)

This follows up an open question from the start of the project: has anyone launched a private-suite harness monitor? Star counts come from the GitHub API on 2026-09-27. "No" means the feature was not found in the README or docs. **Re-verify every row before it appears in a README comparison table.**

## Known players

| Name | Stars | Licence | Private suites | Scheduling | Harness-version pinning | Statistical alerts |
|---|---|---|---|---|---|---|
| Harbor (+ Hub) | 5,627 | Apache-2.0 | Yes (Hub publishes privately) | No cron; Hub runs hosted jobs | Agent `version` option, no matrix | No |
| Margin Eval | 150 | AGPL-3.0 | Yes (local suites) | No | Per-run config | No |
| MarginLab trackers | closed | – | No product found (`/pricing` returns 404) | Daily, public SWE-Bench-Pro subset | No ("latest release") | Yes (p < 0.05, email) |
| AIStupidLevel | 105 | MIT | No (models through the API) | Yes | N/A | Page-Hinkley, public |
| Artificial Analysis Coding Agent Index | closed | – | No | Updated per version | Harness × model pairs | No |
| Entire CLI | 5,124 | MIT | – | – | – | No drift features |
| Imbue Vet | 516 | AGPL-3.0 | – | – | – | No drift features |

## New since roughly June 2026

- **[UiPath/coder_eval](https://github.com/UiPath/coder_eval)**: 141★, Apache-2.0, created 2026-07-09, release 0.12.7 on 2026-09-25. **This is the closest overlap.**
  - Covers Claude Code, Codex, OpenCode, Antigravity and Pi, with your own YAML tasks and A/B experiments with replicates.
  - Statistics: a Welch t-test, bootstrap CIs and Wilson intervals.
  - Cost and token telemetry, budget errors, and a recommended scheduled "drift run" in GitHub Actions. It pins the Claude Code CLI in its Docker image.
  - **Not found:** runs triggered by releases, a version-matrix time series, sequential stopping, or Slack or GitHub-issue alerts.
- **[jameskomo/config-drift-checker](https://github.com/jameskomo/config-drift-checker)**: 26★, FSL-1.1-Apache-2.0, created 2026-08-27.
  - Runs a canary on every Claude Code release against a pinned baseline, with `drift-bisect`, noise bands, and Slack and PR alerts.
  - Scoped to *config* (CLAUDE.md, skills, hooks) written as eval cases, not to task suites. Claude Code first.
- **[SLP-DEV1/claude-code-canary](https://github.com/SLP-DEV1/claude-code-canary)**: 1★, MIT. Release watch, bisection, and token and cost regressions. Claude Code only.
- **[minghinmatthewlam/openbench](https://github.com/minghinmatthewlam/openbench)**: 136★, MIT. A harness comparison scaffold that builds on Harbor. It records `harness_version` and reports Wilson CIs. No scheduling.
- **Anthropic `claude plugin eval`** (Claude Code 2.1.269, 2026-09-11). A first-party with/without-plugin eval: 3 runs per arm, a cost cap, records `claudeVersion`. Claude Code only, scoped to plugins, run by the vendor.
- **One-off public harness comparisons:** FrontierHarness Eval (282★, HN 82 points) and HarnessTax (HN 232 points). Snapshots like these weaken the novelty of a *snapshot* "efficiency index". A time series is still new.
- **Name collision:** runcanary.ai (YC) uses "canary" for PR-time AI code verification. Two of the GitHub repos above also use "canary".

## Implications

1. **The full combination is still unowned.** No project with 50 or more stars combines all of these:
   - private task suites
   - a harness-version matrix across Claude Code, Codex and OpenCode
   - release and cron triggers
   - sequential stopping plus cost CIs
   - alerts
   - Apache-2.0
2. **The gap is narrower than the 2026-09-27 report said.** Each piece now exists in some young project.
3. **The closest overlap is coder_eval.** It is corporate-backed, ships weekly and already has most of the execution and statistics surface. The next closest are config-drift-checker (the exact concept, config-scoped) and Harbor Hub (execution plus hosting).
4. **Differences worth measuring:**
   - Detection power per dollar: the anytime-valid sequential test (ADR-0003) and a published regression-injection benchmark.
   - Harness-version attribution through the version matrix.
   - The deterministic false-success verifier.
5. **Open decision:** the working name "canary" collides with at least one YC company and two repos.
