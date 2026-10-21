# Competitive re-check: private-suite harness monitors (2026-10-21)

This re-check updates the 2026-09-27 note (`docs/research/2026-09-27-competitive-recheck.md`). All sources were read on 2026-10-21. They include GitHub repo pages, raw READMEs and docs, commit and release Atom feeds, the npm and PyPI registries, vendor sites, and the Hacker News Algolia API. For several projects the source code was also read from shallow, read-only clones or tarballs. The unauthenticated GitHub REST API had used up its rate limit. So star counts come from the `stargazerCount` field in each github.com repo page. Harbor's count was also checked against the GitHub search API, and Arena's count comes from that API alone. In the table, "No" means the feature was not found in the docs or code read. It does not prove the feature is absent. "Partial" means part of the feature exists, as the cell explains. Star counts and dates go stale fast. **Re-verify every row before quoting it in a README, blog post or launch.**

## Players

| Name | Stars | Licence | Latest activity | Private suites | Harness-version matrix | Triggers | Statistics | Cost | Alerts | Claim checking |
|---|---|---|---|---|---|---|---|---|---|---|
| [UiPath/coder_eval](https://github.com/UiPath/coder_eval) | 153 | Apache-2.0 | v0.12.14 on 2026-10-15; commit 2026-10-19 | Yes (YAML) | Partial: the CLI version is pinned per release and recorded in `run.json`. Variants cannot vary it. | Partial: cron in GitHub Actions (commented example). No release triggers. | Fixed-sample: replicates, bootstrap and Wilson CIs, Welch or paired test. Computed only when the report renders. | Yes: re-priced from run artifacts; per-task USD and token caps | No | No (docs only; source not grepped) |
| [jameskomo/config-drift-checker](https://github.com/jameskomo/config-drift-checker) | 32 | FSL-1.1-ALv2 | v1.5.3 on 2026-10-16; automated commit 2026-10-20 | Partial: config and plugin-eval cases | Partial: Claude Code versions × models (`drift-matrix`, manual only) | Yes: watches npm releases; cron every 6 h | None formal: two-stage run expansion, max-minus-min noise band, median thresholds | Partial: vendor-reported cost; per-run and per-month caps from a ledger; null for Codex and Gemini | Yes: Slack, job summary, drift index | No |
| [dshakes/halos](https://github.com/dshakes/halos) | 0 | Apache-2.0 | v0.2.1 on 2026-10-12; last commit the same day (UTC) | Yes (`task.yaml`) | Yes: harness × pinned version × models × settings × provider | Yes: `upgrade watch` on the npm `latest` dist-tag, every 6 h by default. The code says this is not yet verified against the real npm registry. | Offline suite: fixed-sample paired bootstrap. mSPRT is used only for live-traffic experiments. | Partial: as each harness reports it; Codex cost recorded as 0; per-task `budget_usd` | Partial: Slack and webhook for rollouts and experiments; no alert when an upgrade is blocked | No |
| [minghinmatthewlam/openbench](https://github.com/minghinmatthewlam/openbench) | 137 | MIT | Last commit 2026-08-27; version-check cron last ran 2026-10-20 | Yes (Harbor-native) | Partial: one CLI version set per dataset, with drift gates | Partial: a weekly npm-latest check files a GitHub issue but does not start runs | Fixed-sample: Wilson. Task-level bootstrap on cost and latency, Gateway Bench only. | Partial: re-priced from input and output tokens; cache tiers not priced | Partial: one GitHub issue for version bumps | No (hack sweeps are judged by an LLM or a person) |
| [TITANS-COVENANT/arbiter](https://github.com/TITANS-COVENANT/arbiter) | 0 | MIT | Last commit 2026-09-11; no releases | Yes (YAML) | No | No (PR-time CI gate) | **Sequential**: paired McNemar SPRT with a simple alternative, Ville anytime p-value, e-BH FDR, Robbins confidence sequence | Partial: `max_cost_usd` and `max_seconds` caps; cost is not compared between builds | Partial: exit codes, step summary, PR comments | No |
| [Harbor](https://github.com/harbor-framework/harbor) | 6,311 | Apache-2.0 | Push 2026-10-21; v0.24.0 on 2026-10-05 | Yes | Partial: versions pinned when a hosted job is submitted; versions passed via kwargs; `-m` expands across models | No | None merged (mean, sum, min, max). PRs #517, #2361 and #2714 are open. | Yes: tokens plus LiteLLM pricing; no caps | No | No (`harbor analyze` uses an LLM judge) |
| [Margin Eval](https://github.com/Margin-Lab/evals) | 162 | AGPL-3.0 | Last commit 2026-07-31 | Yes | Partial: exact version per run in direct mode | Partial: cron only in MarginLab's internal tracker code | Product: none. Internal tracker: fixed-sample exact binomial test against a fixed baseline, plus Wilson. | Partial: tokens; dollar cost only when the agent reports it; none for Claude Code | No (a hook fires on run failure, not on regression) | No |
| [MarginLab trackers](https://marginlab.ai/trackers/claude-code/) | Closed | Proprietary | Last data 2026-09-29 | No | No (always the latest release) | Partial: daily; detection paused | Fixed-sample Wilson and p < 0.05, repeated over 1-, 7- and 30-day windows | Partial: tokens and runtime; no dollars | Partial: email | No |
| [mupt-ai/self-bench](https://github.com/mupt-ai/self-bench) | 33 | MIT | Commit 2026-10-20; deploy release 2026-10-21 | Yes (built from merged PRs, Harbor-native) | Partial: model × harness × reasoning level; harness CLI version neither pinned nor recorded | No | None (one attempt per setting; Pareto frontier) | Yes: re-priced from tokens; append-only re-pricing | No | No |
| [Promptfoo](https://github.com/promptfoo/promptfoo) (owned by OpenAI) | 26.2k | MIT | 0.124.1 on 2026-10-08 | Partial: your own test cases | No (Codex SDK pinned with a caret range) | Partial: GitHub Actions cron example | None (`--repeat` to see variance) | Partial: estimated for known models; threshold assertions | Partial: PR comment | Partial: trace assertions, e.g. "ran tests" |
| [Anthropic `claude plugin eval`](https://code.claude.com/docs/en/plugin-evals) | Closed | Proprietary | Claude Code 2.1.306 on 2026-10-21; last plugin-eval change in 2.1.299 | Partial: plugin cases | No (records `claudeVersion`) | No | Fixed: 3 runs per arm, mean delta, no inference | Yes: list-price `costUsd`; `--max-cost-usd` | No | No |
| [Anthropic claude-api skill: build-eval and hillclimb](https://claude.dev/blog/automating-eval-design-and-hillclimbing/) | 182,528 (whole anthropics/skills repo) | Apache-2.0 | Commit 2026-10-09 | Yes (for a Claude-powered app) | No | No | Fixed-sample CIs and a noise-floor check; CI method not specified | Yes: tokens × price | No | No |
| [SLP-DEV1/claude-code-canary](https://www.npmjs.com/package/claude-code-canary) | Not readable (repo returns 404) | MIT | npm 2.1.0 on 2026-10-09; GitHub repo gone by 2026-10-21 | Yes | Partial: exact Claude Code releases; bisection | Partial: release watch runs once per call; no scheduler | None: fixed thresholds, single runs | Partial: reported cost; per-run and per-scenario caps | No (none in the package) | No |
| [Abelo9996/rerun-bench](https://github.com/Abelo9996/rerun-bench) | 0 | MIT | Last commit 2026-10-07 | Yes (`--tasks-dir`) | Partial: records the CLI version; `bin=` selects a build | No (PR and manual trigger only) | Fixed: Wilson; bootstrap on macro pass rate; pass@k, flip rate | Partial: CLI-reported cost; Codex priced via options | No | No (claims recorded, not scored) |
| [Abelo9996/nerf-watch](https://github.com/Abelo9996/nerf-watch) | 0 | MIT | Last commit 2026-10-07 | No (reads local session logs) | Partial: baselines per CLI version and model | Partial: menu-bar app checks every 30 min | Fixed thresholds on medians | Partial: tokens only | Partial: macOS notification | Partial: deterministic phantom-edit check (edit claims, not "tests pass") |
| [macanderson/arena](https://github.com/macanderson/arena) | 1 | MIT | Dependabot commit 2026-10-18; last author commit 2026-09-29 | Partial: fixtures added to your own clone | Partial: records `--version`; does not pin | No | Fixed: Wilson, exact McNemar, paired bootstrap on deltas; the gate checks for CI overlap | Yes: shared pricing table | No | No |
| [duthaho/vibecheck](https://github.com/duthaho/vibecheck) | 0 | MIT declared; no LICENSE file | Last commit 2026-08-24 | Partial: `--pack` | Partial: records `claude_code_version`; verdict pools all versions | Partial: nightly cron example | Fixed two-proportion z-test re-run nightly, with no multiplicity correction; Wilson | No | No | No |
| [AIStupidLevel](https://aistupidlevel.info/) | 111 (web app repo) | MIT (web app); backend closed | Commit 2026-10-20 | Partial: contracted, vendor-run, models only | No | Partial: vendor schedule | Page-Hinkley; hourly Welch t-test; ±1.96 SE | Yes (cost per correct fix) | Yes: email, webhooks | No |
| [Artificial Analysis Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents) | Closed | Proprietary | Data updated on or after 2026-10-03 | No | Partial: versions recorded in page data; 10 of 42 rows pool several versions | No | None: 3 attempts per task, means only | Yes: pay-per-token | No | Partial: LLM judge (`harbor analyze`) for reward hacking |
| [Artificial Analysis Optima](https://artificialanalysis.ai/optima) | Closed | Proprietary (Pro plan, $417/month per seat) | Article dated 2026-08-13 | Yes (your files, datasets, traces) | Not stated | Not stated | Not stated (rubric or pairwise LLM judge) | Yes: cost per task | Not stated | No |
| [FrontierHarness Eval](https://github.com/frontier-harness-eval/eval) | 316 | None declared | Last commit 2026-09-08 | Partial: task directory plus custom `--cmd`; needs Runta | Partial: versions recorded; one model | No | None (one attempt per cell) | Yes: re-priced from a frozen price table | No | No |
| [HarnessTax](https://harnesstax.github.io/) | 1 | None declared | Last content change 2026-09-21 | No | Partial: 3 harness versions recorded | No | Fixed: task-level bootstrap (10,000 resamples) over 30 tasks | Yes: re-priced from a frozen price list | No | No |
| [Entire CLI](https://github.com/entireio/cli) | 5,194 | MIT | v0.11.6 on 2026-10-20 | No | No | No | None (token delta between two checkpoints) | Partial: tokens | No | No |
| [Imbue Vet](https://github.com/imbue-ai/vet) | 522 | AGPL-3.0-only | Last commit 2026-09-14 | No | No | No | None (LLM confidence threshold) | Partial: caps its own review spend | No | Partial: one LLM prompt checks for misleading behaviour, including false test claims |
| [runcanary.ai](https://www.runcanary.ai/) | Closed | Proprietary; npm CLI declares Apache-2.0 | CLI 0.1.14 on 2026-09-25 | No | No | Partial: on PRs; scheduled app tests | None | No | Partial: Slack, Linear | Partial: LLM QA via `canary verify` |

## What changed since 2026-09-27

**Changes**
- **coder_eval:** 141 to 153 stars. Releases v0.12.8 to v0.12.14 (2026-09-29 to 2026-10-15) added:
  - anti-cheat fixes
  - agent wall time reported separately from grading time
  - a context-window cap
  - pricing for Haiku 5.5, Sonnet 5.5 and GPT-6.1 Sol

  Its Docker image pins Claude Code 2.1.281 and records the CLI version per run. It still has no release triggers, no sequential test and no alerts.
- **config-drift-checker:** 26 to 32 stars. Releases v1.4.0 to v1.5.3 (2026-10-01 to 2026-10-16) added `drift-matrix` (Claude Code versions × models), a context-cost record on every run and `usage-check`. Its public observatory shows "$15.19 of $15 this month". The last behavioural canary ran on 2026-10-12, at 2.1.296. Automated commits continue.
- **Harbor:** 5,627 to 6,311 stars. v0.24.0 (2026-10-05) added `harbor run --diff`, `--effort`, Pareto and Outcomes views, and rewardkit cost estimation. Statistics are still only in open PRs #517, #2361 and #2714 and open issue #1330.
- **MarginLab trackers:** both trackers show "Degradation detection is paused" while they collect new baselines (Opus 5.5 high, GPT-6 Sol high). No data has been published since 2026-09-29. The Codex widget still labels drops against the old baseline "Statistically Significant".
- **Margin Eval:** 150 to 162 stars. No commits since 2026-07-31.
- **AIStupidLevel:** 105 to 111 stars. A $1,290 one-off assessment on the customer's tasks was committed on 2026-09-27. A landing page advertising drift alerts on your own suite was created on 2026-10-15.
- **Entire CLI:** 5,124 to 5,194 stars. Released v0.11.5 (2026-10-14) and v0.11.6 (2026-10-20), with review profiles, more redaction and token-count fixes. No eval or drift features.
- **Imbue Vet:** 516 to 522 stars. No activity since 2026-09-14.
- **Anthropic `claude plugin eval`:**
  - 2.1.299 (2026-10-14) added `--disallow-tools`, and a run that ends on an API error now scores 0.
  - 2.1.300 added OTel GenAI attributes and the 5-minute and 1-hour cache-write token split on `api_request`.
  - 2.1.296 cut the Sonnet 5.5 cache-read price in `/cost` to $0.10/M.
  - Latest is 2.1.306 (2026-10-21).
- **SLP-DEV1/claude-code-canary:** the GitHub repo, the account and the Marketplace Action returned 404 on 2026-10-21. The account was live in a Wayback snapshot on 2026-10-14. The npm package remains, with 2.1.0 published 2026-10-09 and 298 downloads from 2026-09-19 to 2026-10-18.
- **FrontierHarness Eval:** 282 to 316 stars. No maintainer commits since 2026-09-08. Community PR #13 is still open.
- **HarnessTax:** six publishes from 2026-09-22 to 2026-10-14 changed only a timestamp. The results have not changed since 2026-09-21. The promised traces are not public.
- **openbench:** 136 to 137 stars. No code commits since 2026-08-27.
- **Codex CLI context (supports the problem statement):**
  - rust-v0.161.0 (Oct 7) made GPT-6.1 Sol the default model.
  - rust-v0.163.0 (Oct 15, timezone not shown) turned Daybreak on by default for eligible accounts.

  These are harness-default changes, announced in release notes.

**Corrections to the 2026-09-27 check**
- **coder_eval:** v0.12.1 (2026-09-12) already added a Harbor export and a coder_eval agent for Harbor. The check missed this.
- **config-drift-checker:**
  - Codex and Gemini adapters arrived in v1.1.0 (2026-09-26) and are experimental, with no cost data.
  - GitHub-issue alerts were not found in the code. The alerts are Slack, PR comments and the job summary.
- **openbench:** a weekly cron job has checked npm for new CLI versions and filed a GitHub issue since 2026-07-21. "No scheduling" was incomplete.
- **Margin Eval:**
  - The repo contains cron and fixed-baseline binomial test code for MarginLab's own tracker.
  - Versions can be pinned exactly per run, not only through config.
- **AIStupidLevel:** a contracted "custom continuous benchmarking" offer on the customer's own work was committed on 2026-09-16. "Private suites: no" should read "vendor-run, models only".
- **Artificial Analysis:** harness versions are in the page data, though not displayed. The index pools versions in 10 of 42 rows.
- **runcanary.ai:** its Launch HN post says it schedules and runs app test suites continuously. Its npm CLI installs a binary named `canary`.

## New since 2026-09-27

Closest overlaps first. Items marked "missed" existed before 2026-09-27 but were not in the earlier check.

- **[dshakes/halos](https://github.com/dshakes/halos)** (first commit 2026-09-30, 0 stars, Apache-2.0). This is the closest prior art for the full canary loop: a new CLI release appears, your private suite runs on the pinned candidate, and you get a statistical verdict.
  - It has a harness × version × model × settings matrix.
  - It watches the npm `latest` dist-tag.
  - It runs a paired bootstrap on pass rate, cost, tokens and time, with a non-inferiority margin.
  - Its mSPRT applies only to live-traffic experiments, not to the suite pass rate.
  - Codex cost is recorded as 0.
  - It has no OpenCode support, no Harbor execution, no false-success verifier, no run bundles and no alert when an upgrade is blocked.
  - It has one maintainer and no commits since 2026-10-12.
- **[TITANS-COVENANT/arbiter](https://github.com/TITANS-COVENANT/arbiter)** (missed; built in one day, 2026-09-11; 0 stars; MIT). A sequential CI gate for agent evals.
  - It uses a paired McNemar SPRT with a simple alternative, a Ville anytime p-value, e-BH FDR control across a suite, and a Robbins confidence sequence.
  - Its simulation used 40% fewer replicates than a fixed-sample design with the same correction. Against an uncorrected fixed-sample design it used 10.6% more.
  - It has no harness adapters, no triggers, no cost intervals and no claim checking.
- **[Promptfoo](https://github.com/promptfoo/promptfoo)** (missed; acquired by OpenAI, announced 2026-03-09; 26.2k stars; MIT).
  - OpenAI's docs name Promptfoo as the migration path from the hosted Evals platform. That platform goes read-only on 2026-10-31 and shuts down on 2026-11-30.
  - Promptfoo runs the Codex SDK, the Claude Agent SDK and the OpenCode SDK on your own cases.
  - It offers `--repeat`, cost and latency thresholds, trajectory assertions and CI cron examples.
  - It has no version matrix, no statistics and no release triggers.
- **[mupt-ai/self-bench](https://github.com/mupt-ai/self-bench)** (missed; created 2026-07-12; 33 stars; MIT).
  - Builds private, Harbor-native suites from your repo's merged PRs.
  - Ranks model × harness × reasoning settings by accuracy and re-priced cost.
  - Runs each task once per setting, with no statistics, no triggers and no harness-version pinning.
- **[Abelo9996/rerun-bench](https://github.com/Abelo9996/rerun-bench)** (created 2026-10-03; 0 stars; MIT).
  - Reruns your own tasks on Claude Code, Codex and OpenCode, and records CLI versions.
  - Reports fixed-sample Wilson and bootstrap intervals on pass rate.
  - Its roadmap lists version-over-version tracking with per-task significance tests.
- **[Abelo9996/nerf-watch](https://github.com/Abelo9996/nerf-watch)** (created 2026-10-03; 0 stars; MIT).
  - Reads local Claude Code and Codex logs and flags regressions at CLI-version boundaries, using fixed thresholds.
  - Its deterministic `phantom` command flags claimed edits that had no edit-capable tool call. It does not check "tests pass" claims.
- **[Anthropic claude-api skill: build-eval and hillclimb](https://claude.dev/blog/automating-eval-design-and-hillclimbing/)** (blog post 2026-09-28; commit 2026-09-29; Apache-2.0). First-party. It builds a private eval for a Claude-powered app, with confidence intervals, a 1/√(n·R) noise floor and cost. It has no harness under test, no triggers and no alerts.
- **[duthaho/vibecheck](https://github.com/duthaho/vibecheck)** (missed; code written 2026-08-08; dormant since 2026-08-24; 0 stars). A self-hosted nightly Claude Code canary that calls itself "the decentralized complement" to MarginLab. It uses a two-proportion z-test re-run nightly, with no cost tracking and no alerts.
- **[macanderson/arena](https://github.com/macanderson/arena)** (missed; created 2026-07-12; 1 star; MIT).
  - Has a baseline gate with Wilson intervals, exact McNemar, a paired bootstrap and re-priced cost.
  - Its docs claim that "no benchmark harness offers a significance-aware gate over held-out, executable verification".
- **[Artificial Analysis Optima](https://artificialanalysis.ai/optima)** (missed; 2026-08-13). Custom, LLM-judged benchmarks on your own data, comparing models on quality and cost per task. Its pages name no harness and mention no scheduling or alerts.

## Implications

1. **The full combination is still unowned, but the gap is now narrow.** No project read today combines all eight pieces: private suites, a harness-version matrix, release and cron triggers, an anytime-valid sequential test, cost intervals, alerts, a false-success verifier and Apache-2.0.
   - Halos comes closest. It has private suites, the matrix, release triggers, cost intervals, partial alerts and Apache-2.0.
   - What remains unowned in one tool:
     - an anytime-valid test on suite pass rate
     - a deterministic "tests pass" verifier
     - Claude Code, Codex and OpenCode together through Harbor
     - cost re-priced from tokens, alongside cost intervals
     - a lifetime spend ledger
     - checksummed run bundles
2. **coder_eval is still the biggest threat.**
   - It has the most overlap with real adoption: 153 stars, weekly releases and a corporate owner.
   - It already integrates with Harbor, pins and records the harness CLI version, re-prices cost, caps spend per task and documents cron runs.
   - A harness-version axis is cheap for it to add, because its Dockerfile already takes the version as a build ARG.
   - Halos is the closest concept but has 0 stars and one maintainer.
   - Promptfoo is the distribution threat: OpenAI owns it, it has 26.2k stars and it already runs all three harness SDKs.
   - Harbor would move much closer if any of the open statistics PRs were merged. Watch #517, #2361, #2714 and #1330.
3. **Claims the launch README must not make.** Each of these now exists elsewhere:
   - First to watch releases and bisect: SLP-DEV1/claude-code-canary.
   - First with a harness × version × model matrix and release triggers: Halos, and config-drift-checker for Claude Code.
   - First with sequential stopping for agent evals: arbiter.
   - First to detect false test claims: Imbue Vet markets this, and nerf-watch detects phantom edits deterministically.
   - First self-hosted private-suite canary: vibecheck.
   - First to re-price cost from tokens: Harbor, coder_eval, openbench, SelfBench, FrontierHarness and HarnessTax.
4. **Where to differentiate in the launch README:**
   - **The combination**, in one Apache-2.0 tool on top of Harbor, covering Claude Code, Codex and OpenCode at exact pinned versions. Compare FSL (config-drift-checker) and AGPL (Margin Eval, Vet).
   - **Sequential testing on suite pass rate, measured honestly.**
     - Compare a mixture e-process against arbiter's simple-alternative SPRT, and against fixed-sample tests repeated on sliding windows. MarginLab and vibecheck do this repeated testing without correction.
     - Report detection power against runs and dollars on the three injected postmortem regressions.
     - Use Anthropic's 1/√(n·R) noise floor as a stated baseline.
   - **A deterministic "tests pass" verifier**: a test-runner tool call that exits 0 after the last edit. Report false-success rates per harness version. Vet's check is an LLM judgement, and nerf-watch checks only edit claims.
   - **Cost governance of the canary itself**: cluster-bootstrap intervals on re-priced cost, plus a lifetime ledger. Config-drift-checker's own public observatory went over its monthly cap ($15.19 of $15).
   - **Independence**: Anthropic (plugin eval, claude-api skill) and OpenAI (Promptfoo) each now ship eval tooling. The canary does not belong to a vendor whose harness it measures.
   - **The harness efficiency index**: frame it as a time series with versions attributed, not as a snapshot. Artificial Analysis, HarnessTax and FrontierHarness already publish snapshots. Artificial Analysis pools several harness versions into one row in 10 of 42 rows, and shows "Harness Comparison: Coming soon".
5. **Name collision is now concrete.** The runcanary.ai CLI installs a binary named `canary`, the same command as this project's `[project.scripts] canary`. Decide on a rename or record the choice in an ADR before launch.
   - **Added after the sweep (checked 2026-10-21):** the PyPI name `agent-canary` is taken, by an unrelated scanner for unguarded tool calls (`Diplomat-agents/agent-canary`, 0.1.0). So the distribution name has to change whatever the command is called.

## Added after the sweep

- **[qualixar/agentassay](https://github.com/qualixar/agentassay)** (6 stars, AGPL-3.0, read 2026-10-21). Statistical regression testing for agents built on frameworks (LangGraph, CrewAI and others): behavioural fingerprints, a calibration run that sets the number of trials, and offline analysis of production traces. Its README mentions SPRT once. It has no coding-agent harness adapters, no version pinning, no triggers and no alerts. It is not a close competitor, but it shows "statistical guarantees at lower token cost" is a claim others make too.
