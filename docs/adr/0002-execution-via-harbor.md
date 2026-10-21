# ADR-0002: Execute trials through Harbor's CLI, in an isolated environment

- Status: Accepted
- Date: 2026-09-27
- Evidence: [spike 0001](../spikes/0001-harbor-claude-code.md)

## Context

The v0.1 brief rules out a new task runner. Harbor ([harbor-framework/harbor](https://github.com/harbor-framework/harbor), Apache-2.0, about 5.6k stars) runs agents on tasks in parallel sandboxes. We read Harbor 0.23.0 (the PyPI release as of 2026-09-27, commit `d10ac31`) and ran it. What matters for this decision:

- **Licence.** Apache-2.0, compatible with ours.
- **Task format.** A task is a directory:
  - `task.toml` (`schema_version = "1.4"`: timeouts, resources, MCP servers)
  - `instruction.md`
  - `environment/Dockerfile`
  - `tests/test.sh`, which writes `/logs/verifier/reward.txt`
  - optionally `solution/solve.sh`, used by the built-in `oracle` agent
- **Harness adapters exist.** `claude-code`, `codex`, `opencode` and about 40 others are built in. Each takes a `version` option that installs that exact CLI version inside the sandbox. Claude Code also exposes `reasoning_effort`, `append_system_prompt`, `max_budget_usd`, MCP servers and skills. These are the knobs the regression-injection benchmark needs.
- **Per-trial output.** Each trial writes `result.json` with:
  - the installed agent version
  - `n_input_tokens`, `n_cache_tokens`, `n_output_tokens` and `cost_usd`; Claude Code's cost is taken from its own `total_cost_usd`, with a LiteLLM estimate as fallback
  - timings for environment setup, agent setup, agent execution and verifier
  - rewards and exception info

  It also writes a `lock.json` with the task digest, and an ATIF `trajectory.json`. ATIF is a harness-neutral transcript format, which the verifier-lite scorer can consume later.
- **Multiple agents per job.** One job config (`harbor run -c job.yaml`) can list several agents, so one job can hold both arms of an A/B test.
- **The Python API is not a stable contract.** The SDK reference page says "coming soon". The unreleased changelog has several breaking changes, such as agent options now being validated and RewardKit scoring being reorganised. Minor releases ship about every two weeks and may break things.
- **Heavy dependencies.** Harbor depends on LiteLLM, FastAPI, Supabase and about 80 packages in all. `pip install harbor==0.23.0` resolved `litellm 1.102.1`, not the `1.93.0` in Harbor's own lockfile, so unpinned transitive dependencies drift.
- **Harbor configures the harness.** Its Claude Code adapter runs `claude --print --output-format=stream-json` with `bypassPermissions`, `IS_SANDBOX=1` and `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`. A Harbor upgrade can therefore change harness behaviour.

## Decision

1. **Harbor is the execution layer, reached through its CLI and on-disk job format, never its Python API.** For each batch pinbench writes a Harbor `JobConfig` YAML, runs `harbor run -c <file> -y -q` and parses the trial directories it produces. The process boundary is the contract.
2. **Harbor lives in its own hash-locked tool environment** (`tools/harbor/`, pinning `harbor==0.23.0` and `litellm==1.93.2`, wheels only) and is invoked as `uv run --project tools/harbor --frozen harbor`. LiteLLM 1.93.2 rather than the 1.93.0 in Harbor's lock, because 1.93.0 ships no macOS wheels and would compile a Rust extension from source. The command is configurable (`[runner] harbor_command`).
3. **The suite format is Harbor's task format.** `pinbench.toml` adds only suite metadata, pins and budgets. There is no second task format to learn or convert.
4. **We parse Harbor's JSON with our own tolerant models** (Pydantic, `extra="ignore"`, only the fields we use). Contract tests run them against fixtures captured from a real Harbor run. After every trial pinbench checks that the harness version that actually ran equals the pinned version. A mismatch is recorded as pin drift and fails the run rather than being silently compared. The running version is read from the harness's ATIF transcript, because Harbor's `agent_info.version` only echoes the requested version when one is pinned (spike 0001, section 3a).
5. **One Harbor job per batch holds every arm.** Both arms then run in the same time window, which controls for API-side drift during the day, and each task image is built once. Trials map back to pins by agent name, model and options. pinbench refuses to run pins it cannot tell apart. Exception: pins on different Claude Code versions run as one concurrent job per version, so each can mount its own cached binary (ADR-0006).
6. **The Harbor version is part of what a run records.** It is written into every run bundle. Harbor upgrades go through a canary comparison, because they can change how a harness is launched.
7. **Execution sits behind a `Runner` protocol.** A `SimulatedRunner` implements it for tests and power analysis. Other back-ends (Margin Eval, Inspect) can be added without touching statistics or storage.

## Consequences

- No runner code to own. Sandbox providers (Docker, Daytona, Modal, E2B and more) come with Harbor.
- A Harbor upgrade is an explicit change to `tools/harbor/uv.lock` plus a fixture refresh. If contract tests fail, the schema moved.
- LiteLLM and the rest of Harbor's tree never enter pinbench's own environment or lockfile.
- Spawning one process per batch costs seconds. That is negligible next to trials that take minutes.
- Harbor installs the harness CLI from npm or Anthropic's bootstrap script inside the sandbox at runtime. That needs network access and trusts Harbor's installer. Checking the installed version limits the damage but does not remove it. A later ADR can add pre-built harness images.
- The harness under test is "Claude Code as Harbor launches it", not a developer's interactive setup. The report must say so. This is a limitation for questions about interactive use, and it is fine for the regression-detection use case.

## Alternatives considered

- **Harbor's Python API in-process.** Tighter integration, but no stable contract, and Harbor's dependency tree would share our process and lockfile.
- **Harbor as a normal dependency in our `uv.lock`.** Simpler setup, but it pulls about 80 packages, including LiteLLM, into pinbench's environment and couples our release cadence to Harbor's.
- **Margin Eval as the runner.** It has comparable features, but it is AGPL-3.0 and has a smaller ecosystem. It could be added later as an external `Runner` without embedding it.
- **UiPath coder_eval as the runner.** It is Apache-2.0 and has multiple harnesses, but it is young and overlaps with pinbench's own scope. See the [competitive re-check](../research/2026-09-27-competitive-recheck.md).
- **Our own runner.** Explicitly out of scope.
