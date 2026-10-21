# Spike 0001: Harbor as the execution layer, and Claude Code at a pinned version

> The project was renamed from "agent canary" to **pinbench** on 2026-10-21 ([ADR-0010](../adr/0010-name-pinbench.md)). This record keeps the names used at the time: `canary` is now `pinbench`, and `canary.toml` is `pinbench.toml`.

- Date: 2026-09-27
- Goal (brief, step 3): run one task through Harbor with Claude Code at a pinned version, and capture tokens, cost and transcript.
- Outcome: **done.** Claude Code 2.1.283 on `claude-opus-5` ran through Harbor and the canary, with tokens, cost and transcript captured (section 3). It took three failed attempts first; each one found a real problem (section 3a). Total API spend: $1.30.

## 1. Harbor, installed and run (done)

- Harbor 0.23.0 from PyPI (`harbor-framework/harbor` at `d10ac31`), Apache-2.0.
- `harbor run -p examples/tasks/hello-world -a oracle` in local Docker gave reward 1.0 in 2 min 32 s. About 35 s went to building the image and about 1 min 43 s to the task's verifier, which runs `apt-get` and installs uv on every trial.
- Output layout per trial:
  - `result.json` (TrialResult: agent info and version, token counts, `cost_usd`, per-phase timings, rewards, exception)
  - `lock.json` (task digest, Harbor version)
  - `config.json`
  - `agent/` (agent logs; `trajectory.json` in ATIF for agents that support it)
  - `verifier/` (`reward.txt`, CTRF, stdout)
  - `trial.log`
- A job-level `result.json` has aggregate stats. Its timestamps are local time without a timezone, while trial timestamps are UTC. The canary reads only trial-level times.
- Captured as a contract fixture: `tests/fixtures/harbor/oracle-job/`, with absolute paths replaced.

## 2. Harbor through the canary (done)

`canary compare oracle nop -c examples/demo-suite` generates one Harbor JobConfig per batch, holding both arms. It runs `harbor run -c … -y -q` from the hash-locked `tools/harbor` environment and maps trials back to pins by agent name, model, options and env. See [Result](#result) below.

Findings that shaped ADR-0002:

- The Python SDK reference is "coming soon", and the unreleased changelog has breaking changes. So the contract is the CLI plus `result.json`, not the Python API.
- `pip install harbor==0.23.0` without a lockfile resolved LiteLLM 1.102.1, not the 1.93.0 in Harbor's own lock. Hence the isolated, hash-locked tool environment.
- **LiteLLM 1.93.0 publishes Linux wheels only.** On an Intel Mac, uv fell back to compiling its Rust extension from source and filled the disk. The tool env now pins LiteLLM 1.93.2 (the same minor line, with macOS wheels), sets `no-build = true` (wheels only, no build scripts), and constrains `cryptography<49` on Intel macOS only. cryptography 49 and later dropped Intel-Mac wheels.
- Harbor forwards a pin's `env` into every harness exec, and echoes non-secret env values literally in each trial's config. So an env-only pin (for example `DISABLE_PROMPT_CACHING=1`) is distinguishable within a shared job.
- **Harbor's `environment.delete: true` runs `docker compose down --rmi local` after every trial,** which deletes the task image. On this machine Docker's layer cache made the rebuild cheap: batch wall time was 70 s with deletion and 61 s without. The first-ever build of a task image took about 65 s (base image pull plus `pip install pytest`). The canary briefly defaulted to `delete: false`; that was reverted (see section 3a). `[runner] keep_images` remains as an option.
- **Per-trial overhead with cached images:** environment setup 6–11 s, verifier 2–3 s, plus 10–14 s of container lifecycle outside the phases Harbor times. With `n_concurrent = 4`, a batch of 6 zero-cost trials takes about 60 s. Real harness trials take minutes of agent time, so this overhead will not dominate.
- Harbor's `--env-file` loads a `.env` into its own process with override. Harbor also silently loads `.env.local` from its working directory, which for the canary is the directory holding `canary.toml`.

## 3a. First Claude Code attempt: failed in setup, cost nothing

Run `20260926T224929Z-run-d439cf`. All 3 trials hit `AgentSetupTimeoutError` after Harbor's default 360 s agent-setup timeout. The model was never called, so no tokens were spent. What happened inside each sandbox:

1. Harbor apt-installed `curl bash nodejs npm procps`, because the task image lacked them.
2. It then downloaded the Claude Code native binary through the bootstrap installer.
3. Three concurrent trials on this machine and network ran past 360 s.

Fixes, and a correction to our own design:

- **Bake the harness prerequisites into task images.** Harbor skips any system package whose command already exists. The demo images now include `curl`, `procps`, `nodejs` and `npm`. The harness binary itself is still installed per trial, so the harness version stays a pin rather than a task property.
- **`[runner] agent_setup_timeout_multiplier`** is passed to Harbor's job config. The demo uses 2.0.
- **The pin-drift check was weaker than ADR-0002 claimed.** `result.json`'s `agent_info.version` read `2.1.283` even though setup failed before anything was installed: when a version is pinned, Harbor echoes the requested version. The canary now reads the running version from the ATIF trajectory (`agent/trajectory.json` → `agent.version`), records `version_source`, and treats a mismatch as drift only when the trajectory proves it. For harnesses without ATIF output, drift cannot be verified, and the report says so.
- The CLI reported "0/3 passed", which hid that these were infrastructure errors. It now reports passed, failed and errored counts plus the exception types.

**Second attempt** (run `20260926T225809Z-run-ed6a2c`, prerequisites baked in, timeout doubled to 720 s): all 3 trials timed out again, inside the Claude Code installer. Again, no tokens were spent. Diagnosis by hand in the same image:

- The installer script downloads in 0.6 s. It then fetches the `latest` binary (241.6 MB for linux-x64), verifies it, and runs `claude install 2.1.283`, which downloads the pinned version again.
- This machine's link measured about 1.1 MB/s, on the host and inside Docker alike. Three concurrent trials × about 480 MB is about 22 minutes.
- **The bottleneck is bandwidth, not Docker.**

Fix: [ADR-0006](../adr/0006-harness-binary-cache.md). Download each pinned binary once on the host, verify its SHA-256 against the release manifest, and bind-mount it read-only into sandboxes.

**`keep_images` reverted.** With Harbor's `delete: false`, each trial leaves its own tagged image, because compose project names are per trial. The two runs left 66 images behind. Layers are shared, so the disk cost was lower than the tags suggest, but they accumulate, and the measured saving was only about 10 s per batch. The default is back to Harbor's normal clean-up, and the leftover images were removed.

**Third attempt** (run `20260926T232705Z-run-824973`, harness cache mounted): the setup problem is solved. The batch took 49 s, and the trajectory proved `2.1.283` was running (`version_source = trajectory`). Every trial then exited after about 3 s with Harbor `UnknownApiError` and 0 tokens. Claude Code's stream showed:

> API Error: 400 This API key is not scoped to a workspace, so this request must include the anthropic-workspace-id header…

So this was a credential problem, and cost was $0. Harbor still ran the verifier and wrote reward 0, so the canary counted these as *failures*. That would bias a comparison against whichever arm hits API trouble. Harbor's API, auth, setup and verifier-plumbing exceptions now make a trial `error`, which is excluded from pairing (`INFRASTRUCTURE_EXCEPTIONS` in `runners/harbor.py`). Agent timeouts, context overflows, refusals and crashes still count as failures.

## 3. Claude Code at a pinned version (done)

Run `20260926T233112Z-run-11ff59`: `canary run cc-baseline -c examples/demo-suite --env-file .env`, with the harness cache mounted and a workspace-scoped key. Result: **3/3 passed, 89 s wall time, $0.31.**

| Task | Input tokens (cache reads) | Output tokens | Reported cost | Agent time |
|---|---|---|---|---|
| fix-pagination | 65,294 (58,605) | 709 | $0.089 | 21 s |
| parse-duration | 83,543 (76,080) | 1,199 | $0.115 | 32 s |
| slugify | 67,534 (62,131) | 1,698 | $0.107 | 33 s |

Checklist:

- [x] **Version.** The installed version is 2.1.283, proven by the ATIF trajectory (`version_source = trajectory`).
- [x] **Tokens and cost.** Both are populated. Cost matches tokens × Opus 5 list prices, within the uncertainty of cache writes versus plain input. fix-pagination: 58,605 cache reads × $0.50/M + about 6.7k fresh or cache-write input × $5–6.25/M + 709 output × $25/M comes to $0.080–0.089, against $0.0888 reported.
- [x] **Transcript.** `agent/trajectory.json` (ATIF-v1.7) exists and renders in the report's transcript view.
- [x] **Bash exit status in ATIF.** Each Bash result carries `extra.tool_result_metadata.tool_use_result` with `stdout`, `stderr` and `interrupted`, plus `raw_tool_result.is_error`. **There is no numeric exit code.** Worse for naive checks, the agent ran its tests as `python -m pytest -q test_durations.py 2>&1 | tail -3`, so the shell status is `tail`'s, not pytest's. **Design input for verifier-lite:** a "tests pass" claim must be matched against *test-runner output* (`N passed`, `failed`, `error`) in a test-runner call after the last `Write` or `Edit`. Exit codes are not enough even where harnesses report them.
- [x] **Timing.** Agent time 20–33 s per trial. With the cached harness, environment setup and install is seconds. The batch took 85 s.

A real trial is now a contract-test fixture (`tests/fixtures/harbor/claude-code-job/`, paths sanitised, no credentials).

## 4. First real comparison: `cc-baseline` vs `cc-low-effort` (done)

Run `20260926T233333Z-compare-b16d31`, 2 batches × 3 tasks × 2 arms, $0.99:

| Metric | low-effort / baseline | 95% CI (cluster bootstrap, 3 tasks) |
|---|---|---|
| Pass rate | 6/6 vs 6/6, 0 discordant pairs, E = 1 | Inconclusive, as expected: the demo tasks are too easy |
| Output tokens | ×0.36 | 0.34–0.38 |
| Input tokens | ×0.65 | 0.48–0.77 |
| Agent time | ×0.55 | 0.46–0.74 |
| Reported cost | ×0.89 | 0.61–1.43 |

**Observation:** cost moved much less than tokens. In batch 0 the low-effort trials cost $0.08–0.14; in batch 1, $0.03–0.06. The baseline arm was cheap in both batches, and the spike had run the baseline configuration two minutes earlier.

**Confirmed on 2026-09-30 from the stored transcripts, at no extra spend: this is prompt-cache warmth.** Per-request usage in the ATIF trajectories shows what the first model request of each trial wrote to and read from the prompt cache:

| Arm, batch | Trials | First request: cache write | First request: cache read | Cost per trial |
|---|---|---|---|---|
| `cc-baseline`, batch 0 (ran 2 min after section 3) | 3 | 0 | 15.9k–16.0k | $0.054–0.117 |
| `cc-low-effort`, batch 0, first two trials | 2 | 15.9k–16.0k | 0 | $0.125–0.136 |
| `cc-low-effort`, batch 0, third trial (started 80 s later) | 1 | 3.4k | 12.6k | $0.076 |
| `cc-low-effort`, batch 1 | 3 | 0 | 15.9k–16.0k | $0.034–0.055 |

- A configuration's first trials pay a cache write of about 16,000 tokens (system prompt and tool definitions), which is about $0.10 on Opus 5. Later trials read it back for about $0.008.
- Changing the reasoning effort changes the cached prefix, so the low-effort arm started cold while the baseline arm was already warm.
- The third low-effort trial started after the first two had finished and was already mostly warm. So the penalty falls on the first `n_concurrent` trials of an arm, not on a whole batch.
- The section 3 run, the very first, read about 10k tokens from cache on its first requests. Part of the prefix was already cached before the canary ran anything. The cause is unknown; other Claude Code use on the same workspace is the likely one.

What changed as a result ([ADR-0005](../adr/0005-cost-normalisation.md), now accepted):

- `cost_usd` is re-priced from per-request token usage with the canary's own price table. On all 15 scored trials it reproduces the reported cost, which validates the accounting.
- Cache reads and writes are reported as separate metrics.
- `[stats] warmup_batches` leaves the first batches out of the cost comparison. The demo suite sets 1.

With batch 0 left out, the same data gives a low-effort cost of $0.043 per trial against $0.082 for the baseline. That is 3 trials per arm on three easy tasks: a direction, not a result.

## Result

Oracle vs nop through real Harbor: `canary compare oracle nop -c examples/demo-suite`, 3 tasks, local Docker, zero token cost. Run `20260926T222957Z-compare-deb320`.

| Batch | Trials | Discordant pairs (cumulative) | E | Wall time |
|---|---|---|---|---|
| 0 | 6 | 3 | 3.75 | 57 s |
| 1 | 6 | 6 | 18.14 | 61 s |
| 2 | 6 | 9 | 102 | 51 s |

- **Verdict:** REGRESSION, anytime-valid p ≤ 0.0098, stopped at the first batch boundary past E ≥ 20. Total 2 min 51 s.
- **Outcomes:** oracle passed 9/9 and nop 0/9. No pairs were dropped.
- **Correctness:** every E value matches the closed form in ADR-0003, for example 2⁴/4 · (1 − 2⁻⁴) = 3.75.
- **Bundle:** `canary verify` reports it intact, and the run appears in `canary runs`.

This run used the original mixture bound, q ≤ 1. The bundle's manifest records the settings. With the current default, q ≤ 0.8 (ADR-0003 amendment), the same scenario needs 10 discordant pairs, which is 4 batches. That is what the `docker`-marked integration test in CI (`tests/test_harbor_docker.py`) now asserts.

An earlier identical run reached the same verdict. Its bundle was lost because `make clean` was run while the job was still writing. Do not run `make clean` during a run.
