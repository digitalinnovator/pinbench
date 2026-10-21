# ADR-0008: Triggers are a stateless check plus an external scheduler; alerts are post-seal side effects

- Status: Accepted
- Date: 2026-09-30

## Context

The v0.1 scope asks for two triggers (cron, and detection of new harness releases) and two alert channels (Slack and GitHub issues). pinbench is a CLI with no daemon, and v0.1 must not grow one. Alerts carry credentials, and a pinbench run spends money, so both need clear failure rules:

- A scheduled job that re-tests the same release every day burns the budget for no new information.
- An alert that fails to send must not change or hide a verdict.
- A webhook URL is itself a secret.

## Decision

### Triggers

1. **The scheduler is external.** Cron, GitHub Actions `schedule`, or any CI. pinbench ships one command that is safe to run on a schedule, and an example workflow (`examples/ci/pinbench.yml`). There is no daemon.
2. **`pinbench watch` detects releases.** For each `[watch.<name>]` entry it reads the harness's npm dist-tag (`latest` by default; `stable` for Claude Code) and compares it with the baseline pin's version. Only plain `X.Y.Z` versions are accepted, so alpha, snapshot and per-platform tags are never tested. Without `--run` it only reports, and spends nothing.
3. **The candidate is the baseline pin with only the version changed.** Model, options, env and config files are held fixed, so a verdict is attributable to the release. The derived pin is named `<baseline>-<version>`, exists only for that run, and is recorded in the bundle's manifest like any other pin.
4. **A release is tested once.** After a compare completes, `.pinbench/watch.json` records the version, run id and decision. The next scheduled check skips it unless `--retest` is passed. The state file is a convenience, not evidence: deleting it costs one repeated run, and the bundles remain authoritative (ADR-0004).
5. **Exit codes match `compare`.** 1 if a tested release regressed, 2 on an error, otherwise 0. A registry error in one watch entry does not stop the others.

### Alerts

6. **Alerts run after the bundle is sealed.** They read the verdict and manifest from the bundle. A failed delivery is logged and printed, and does not change the exit code of `compare` or `watch`. `pinbench alert <run_id>` re-sends or previews (`--dry-run`) the alert for any stored run.
7. **Conditions are explicit.** `[alerts] on` lists them: `regression` (the default), `cost_increase` (the cost or latency ratio is flagged by its interval; token counts are reported but do not alert) and `false_success` (more contradicted claims than the baseline, ADR-0007).
8. **Secrets are named, never stored.** `slack_webhook_env` and `github_token_env` hold the *names* of environment variables. The config rejects anything that is not a variable name. Transport errors never include the URL.
9. **GitHub issues de-duplicate by title.** The title is stable per suite and pin pair. If an open issue with that title and the alert label exists, pinbench comments on it instead of opening another.
10. **No new dependencies.** Both channels are plain HTTPS requests through one small module (`pinbench.http`) that refuses non-HTTPS URLs. Tests inject a fake transport; the test suite opens no sockets.

## Consequences

- pinbench has no long-running process to operate, and nothing to secure beyond the CI job's secrets.
- Release detection is only as timely as the schedule. A daily schedule meets the "within a day" goal.
- npm dist-tags are the only release source. Claude Code's native channel (`downloads.claude.ai/.../latest`) can lead npm by minutes to hours, which a daily check does not notice.
- In CI, `watch.json` must be persisted between runs (the example uses the Actions cache). If the cache is lost, one release is tested twice.
- Model releases are not watched. A model change is a new pin that someone writes; a scheduled `pinbench compare` covers it.
- `watch --run` compares two harness versions, which runs as one Harbor job per version so each mounts its own cached binary (ADR-0006). A real two-version run has not been made yet.
- Alert delivery was tested against fake transports only. No real Slack message or GitHub issue has been sent from this code.

## Alternatives considered

- **A built-in scheduler or daemon.** More to run and secure, and every team already has a scheduler.
- **GitHub releases as the release source.** Rate-limited without a token (60 requests an hour), and not every harness tags releases consistently.
- **Webhooks from the registry.** npm has none for public packages without a paid feature.
- **An alerting library (Apprise, slack-sdk, PyGithub).** Two POST requests do not justify three dependency trees in a tool that handles API keys.
- **Alert before sealing, inside the compare loop.** A delivery failure could then abort a run that has already spent money.
