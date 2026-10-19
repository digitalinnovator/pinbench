# Harness telemetry, pinning and release signals (checked 2026-09-27)

These are working notes from a research pass: registry JSON, the CLIs' source and docs, and Harbor 0.23.0's adapters. No prompts were run. Re-verify anything before it goes into a README or blog post. CLI output formats change between versions.

## Claude Code (`@anthropic-ai/claude-code`; `latest` 2.1.283, `stable` 2.1.274)

- **Pinning.**
  - npm: `@anthropic-ai/claude-code@X`.
  - Native installer: `curl -fsSL https://claude.ai/install.sh | bash -s X`. Release manifests are GPG-signed at `downloads.claude.ai/claude-code-releases/<v>/manifest.json`.
  - Packaging changed at **2.1.113 (2026-04-17)**. Up to 2.1.112 the npm package shipped JS (`cli.js`, Node ≥18). From 2.1.113 it ships a native binary through per-platform optional dependencies.
- **March–April 2026 builds.** 53 versions were published. **2.1.88 (2026-03-30) is unpublished.** None are deprecated. Builds published on the postmortem dates:
  - Mar 4: 2.1.66–2.1.69
  - Mar 26: 2.1.85
  - Apr 16: 2.1.111 and 2.1.112

  Native manifests exist for 2.1.64, 2.1.70, 2.1.89 and 2.1.112. **Correction, 2026-09-30:** that list was incomplete. The manifests for 2.1.66, 2.1.69, 2.1.85, 2.1.111 and 2.1.112 all return a linux-x64 build with a checksum (227–241 MB each), so the harness cache can install every build from the postmortem dates. **Not yet verified: whether these builds still behave consistently against today's API.** That is the precondition for the headline replay demo.
- **Headless output.** `claude -p --output-format stream-json --verbose`.
  - `system/init` carries `claude_code_version`, `model`, `session_id`, tools and MCP servers.
  - `result` carries `total_cost_usd`, `duration_ms`, `duration_api_ms`, `num_turns` and `usage`: input, output, `cache_creation_input_tokens`, `cache_read_input_tokens`.
  - `modelUsage[model]` covers subagents too.
- **Cost is a client-side estimate from a price table bundled into each build.** Two builds can report different dollars for identical token counts. See [ADR-0005 (proposed)](../adr/0005-cost-normalisation.md).
- **Bash tool results have no numeric exit code.** A failure sets `is_error: true`, and the content includes the text `Exit code N`. Codex and OpenCode both expose a numeric exit code. This matters for the verifier-lite scorer.
- **Knobs.**
  - `--effort` / `CLAUDE_CODE_EFFORT_LEVEL` (the env var wins)
  - `MAX_THINKING_TOKENS`
  - `DISABLE_PROMPT_CACHING`
  - `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING`
  - `--append-system-prompt`
  - `--max-budget-usd`
  - Auto-update is disabled by `DISABLE_AUTOUPDATER=1`, or by `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, which Harbor sets.
- **OpenTelemetry.** Enable with `CLAUDE_CODE_ENABLE_TELEMETRY=1` plus an exporter.
  - Metrics: `claude_code.token.usage`, `claude_code.cost.usage`.
  - Events: `claude_code.api_request`, `claude_code.tool_result`.
- **Transcripts.** `~/.claude/projects/<slug>/<session>.jsonl`, or under `CLAUDE_CONFIG_DIR`. The format is documented as internal.

## Codex CLI (`@openai/codex`; `latest` 0.157.1)

- **Pinning.** npm `@openai/codex@X`, or `install.sh --release X`. 18 stable versions in March–April 2026, all installable.
- **Headless output.** `codex exec --json`. `turn.completed.usage` is **cumulative** per thread: input, cached, cache_write (after 0.140), output, reasoning (by 0.128). `command_execution` items carry a numeric `exit_code`. **There is no cost, model or version in the JSONL.** The version is in the rollout's `session_meta.cli_version`.
- **Transcripts.** `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`, sometimes zstd-compressed.

## OpenCode (`opencode-ai`; `latest` 1.18.32; repo moved to `anomalyco/opencode`)

- **Headless output.** `opencode run --format json`. `step_finish` carries `cost` and `tokens{input, output, reasoning, cache{read, write}}`. Shell tool calls carry `state.metadata.exit`.
- **Cost uses a price catalogue fetched at runtime from models.dev.** Pin it with `OPENCODE_MODELS_PATH` / `OPENCODE_DISABLE_MODELS_FETCH`, or cost is not reproducible.
- **Auto-update installs patch releases by default.** Disable with `"autoupdate": false` or `OPENCODE_DISABLE_AUTOUPDATE`.
- **Transcripts.** SQLite at `~/.local/share/opencode/opencode.db`.

## Release detection

- Poll npm dist-tags: `GET https://registry.npmjs.org/-/package/<pkg>/dist-tags`. The response is tiny and needs no auth.
  - Claude Code: `latest` and `stable`.
  - Codex: `latest`, ignoring `alpha*`.
  - OpenCode: `latest`, ignoring `snapshot-*`, `dev` and `beta`.
- Claude native channels: `downloads.claude.ai/claude-code-releases/latest` and `/stable`, plain text.
- GitHub releases limit unauthenticated clients to 60 requests an hour. Use a token or ETags.

## What Harbor 0.23.0 extracts

| Adapter | Install | Tokens | Cost | Version |
|---|---|---|---|---|
| `claude-code` | bootstrap.sh or npm `@X` | session JSONL | `total_cost_usd`, falling back to a LiteLLM estimate | session JSONL `version` |
| `codex` | npm `@X` | rollout `token_count` | LiteLLM price table | rollout `cli_version` |
| `opencode` | npm `opencode-ai@X` | summed `step_finish` | summed `step_finish.cost` | `opencode --version` |

None of Harbor's adapters use OTel. Harbor's cost for Codex depends on LiteLLM's price table, which is another reason to pin LiteLLM and to re-price from tokens.
