# ADR-0001: Implementation stack

- Status: Accepted
- Date: 2026-09-27

## Context

pinbench schedules runs of coding-agent harnesses, stores the results, runs statistics over them and renders reports. Its neighbours in the evaluation ecosystem (Harbor, Inspect, SWE-bench, Margin Eval's analysis tooling) are Python. The statistics it needs are sequential tests and bootstrap intervals, which are standard in SciPy and NumPy.

Constraints from the project brief:

- Typed code, tests from the first commit, CI on every push.
- Lockfiles and pinned dependencies, one-command dev setup, no secrets in the repo.
- A small supply-chain surface. The LiteLLM PyPI package was compromised on 2026-03-24, so every dependency is a liability to justify.
- Local, single-team use in v0.1. A hosted service is a non-goal.

## Decision

| Concern | Choice |
|---|---|
| Language | Python 3.12+ (CI tests 3.12 and 3.13) |
| Packaging and environments | uv, with `uv.lock` (hashes for every artifact) and `exclude-newer` set so a re-resolve cannot pick up a package published after the pin date |
| CLI | Typer |
| Data models and config validation | Pydantic v2; config files in TOML (stdlib `tomllib`) |
| Run index | SQLite through the stdlib `sqlite3` module (see ADR-0004 for why it is only an index) |
| Statistics | NumPy and SciPy (see ADR-0003) |
| Report | A static HTML file rendered with Jinja2 and no JavaScript dependencies |
| Logging | Stdlib `logging` with a one-line JSON formatter (`PINBENCH_LOG_FORMAT=json`) |
| Quality gates | ruff (lint and format), mypy `--strict`, pytest |
| Build backend | hatchling |
| CI | GitHub Actions |
| Licence | Apache-2.0 |

Runtime dependencies are pinned exactly in `pyproject.toml`, because this is an application, not a library. There are six direct runtime dependencies. Harbor is not one of them (ADR-0002).

## Consequences

- There are no services to run. `uv sync` sets up the environment, and a run needs only Docker and the Harbor tool environment.
- SQLite is in the standard library, so the index adds no dependency. One scheduler process writes to it. At the expected volume (thousands of trials a month per team) query speed is not a concern.
- Analysts who want columnar queries can attach the SQLite file from DuckDB read-only. Nothing is lost by not shipping DuckDB.
- Strict mypy slows early prototyping a little and catches schema drift between Harbor's JSON and our models early.
- Python start-up time is irrelevant next to agent trials that take minutes.

## Alternatives considered

- **DuckDB as the store.** It is better for analytics, but it adds a native binary dependency and has weaker concurrent-writer semantics. The brief allowed either. SQLite wins on supply chain and simplicity for an index that can be rebuilt. Revisit if the index grows past about 10M rows.
- **Go.** A single static binary is attractive for a CI tool. It would lose SciPy, direct reuse of Harbor's Python ecosystem, and the contributor pool that already writes Python evaluations.
- **TypeScript.** The harnesses ship as npm packages, but its statistics ecosystem is thin and Harbor is Python.
- **Postgres or a hosted store.** A hosted service is a non-goal for v0.1.
- **structlog.** It is nicer, but a 20-line stdlib formatter covers the need without another dependency. Revisit when OpenTelemetry export lands (see the roadmap).
