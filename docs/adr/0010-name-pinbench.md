# ADR-0010: The project is called pinbench

- Status: accepted
- Date: 2026-10-21

## Context

The working name was "agent canary", with the command `canary` and the Python distribution `agent-canary`. By launch it had three collisions:

- **The command.** runcanary.ai, a YC company in AI code verification, ships a CLI that installs a binary named `canary`. A user with both installed would get whichever came first on their `PATH`.
- **The distribution.** `agent-canary` is taken on PyPI by an unrelated scanner for unguarded tool calls (checked 2026-10-21).
- **Search.** Several small canary-named repositories do overlapping work ([competitive re-check](../research/2026-10-21-competitive-recheck.md)).

An earlier check ([naming, 2026-09-27](../research/2026-09-27-naming.md)) left the choice open, with `davylamp`, `linecall` and `refbench` as viable candidates.

## Decision

The project, the distribution, the import package and the command are all **`pinbench`**, written in lower case.

The name says what the tool does: you *pin* an exact harness version, model and configuration, and *bench* it against another pin on your own tasks. "Pin" was already the configuration's word (`[pins.<name>]`). On 2026-10-21 it was free on PyPI, npm and Homebrew. It is not free everywhere: a GitHub organisation named PinBench (created 2026-09-21, with the domain pinbench.dev) makes an Arduino circuit simulator, and `ShadyHippo/PinBench` is a one-star LLM parsing benchmark. The name is kept anyway: the simulator is in another field, this project lives at `digitalinnovator/pinbench` and needs neither the organisation nor the domain, and a second rename before launch would cost more than the overlap.

What changed:

| Before | After |
|---|---|
| `canary` command, `agent_canary` package, `agent-canary` distribution | `pinbench` |
| `canary.toml`, `.canary/` | `pinbench.toml`, `.pinbench/` |
| `$XDG_STATE_HOME/agent-canary/ledger`, `$XDG_CACHE_HOME/agent-canary/harness` (defaults `~/.local/state`, `~/.cache`) | `…/pinbench/ledger`, `…/pinbench/harness` |
| `AGENT_CANARY_LEDGER_DIR`, `CANARY_LOG_FORMAT`, `CANARY_LOG_LEVEL` | `PINBENCH_LEDGER_DIR`, `PINBENCH_LOG_FORMAT`, `PINBENCH_LOG_LEVEL` |
| Manifest field `canary_version` | `pinbench_version`; the old key is still read |
| GitHub issue label `agent-canary` | `pinbench` |

## Consequences

- **Old run bundles stay readable.** Their manifests say `canary_version`, which the model accepts as an alias. Their checksums are untouched.
- **Some names stay as they were, on purpose:**
  - The benchmark tasks' Harbor names (`agent-canary/<task>` in each `task.toml`). They are part of the frozen suite; changing them would change the tasks.
  - The inert `CANARY_ARM` marker in the replicated Codex config. It is part of a pin's fingerprint, recorded in committed runs.
  - Dated records: the benchmark plan and pre-screen (pre-registered), the campaign log, the spike report and the research notes. They describe what was run, under the old command, and carry a note pointing here.
- **"Canary" is still used as a common noun** for this kind of check ("a canary that checks results after every batch"), which is what it is.
- **No compatibility shims for the old paths or environment variables.** Nothing was released under the old name; the one existing ledger was moved by hand.
- **Not checked:** trademark registers. Do that before any wider promotion.

## Alternatives considered

- **Keep "canary" and rename only the command** (for example `agent-canary`). This fixes the binary clash but not PyPI or search.
- **`telltale`** (a dashboard warning light). A better image, but the PyPI name is held by a placeholder, and it competes in search with Telltale Games and about 280 repositories.
- **`harness-canary`.** Free, but Harness Inc. sells "canary deployments", so it reads as their product.
- **`nerfcheck`.** Free and catchy, but "Nerf" is a Hasbro trademark, and the name accuses vendors where the project aims to be a neutral referee.
- **`davylamp`, `linecall`, `refbench`** (the 2026-09-27 shortlist). Viable. `pinbench` describes the mechanism more directly.
