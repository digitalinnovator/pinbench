# Spike 0001: Harbor as the execution layer, and Claude Code at a pinned version

- Date: 2026-09-27
- Goal (brief, step 3): run one task through Harbor with Claude Code at a pinned version, and capture tokens, cost and transcript.
- Outcome: **partial.** Harbor is proven as the execution layer, through the canary, in Docker. The Claude Code trial is prepared but has not run, because no API credential was available in this environment.

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
- **Harbor's `environment.delete: true` runs `docker compose down --rmi local` after every trial,** which deletes the task image. On this machine Docker's layer cache made the rebuild cheap: batch wall time was 70 s with deletion and 61 s without. The first-ever build of a task image took about 65 s (base image pull plus `pip install pytest`). The canary now sends `delete: false` by default (`[runner] keep_images = true`). Containers are still removed; only the images are kept.
- **Per-trial overhead with cached images:** environment setup 6–11 s, verifier 2–3 s, plus 10–14 s of container lifecycle outside the phases Harbor times. With `n_concurrent = 4`, a batch of 6 zero-cost trials takes about 60 s. Real harness trials take minutes of agent time, so this overhead will not dominate.
- Harbor's `--env-file` loads a `.env` into its own process with override. Harbor also silently loads `.env.local` from its working directory, which for the canary is the directory holding `canary.toml`.

## 3. Claude Code at a pinned version (blocked: no credential)

Prepared:

- Pin `cc-baseline` in `examples/demo-suite/canary.toml`: `claude-code` `2.1.283`, `anthropic/claude-opus-5`, `reasoning_effort = "high"`, `max_budget_usd = "1.00"` per trial.
- Harbor's adapter installs that exact version (native bootstrap installer on Debian-based images, npm on Alpine). It runs `claude --print --output-format=stream-json --verbose` with `bypassPermissions`, and reads:
  - tokens from the session JSONL
  - cost from the stream's `total_cost_usd`, falling back to a LiteLLM estimate
  - the version from the session JSONL
- The canary fails the run if the installed version differs from the pin.

To run it, with a key in a gitignored `.env` at the repo root (`ANTHROPIC_API_KEY=...` or `CLAUDE_CODE_OAUTH_TOKEN=...`):

```bash
uv run canary run cc-baseline -c examples/demo-suite --env-file .env
```

The first thing to record from that run:

- [ ] Installed version equals 2.1.283.
- [ ] `n_input_tokens`, `n_cache_tokens`, `n_output_tokens` and `cost_usd` are populated, and cost roughly matches the tokens × the current price list.
- [ ] `agent/trajectory.json` exists and renders in the report's transcript view.
- [ ] How Bash exit status appears in the ATIF observation. It matters for the verifier-lite rule, because Claude Code has no numeric exit code.
- [ ] Wall time per trial and install overhead. Harbor installs the CLI in every trial's sandbox.

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

This is the same scenario as the `docker`-marked integration test in CI (`tests/test_harbor_docker.py`).

An earlier identical run reached the same verdict. Its bundle was lost because `make clean` was run while the job was still writing. Do not run `make clean` during a run.
