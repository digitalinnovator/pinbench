# Commit IDs in run records, and the commits they correspond to now

On 2026-10-21, before the repository was first pushed in its current form, its history was edited:

1. Commit messages lost an attribution trailer (15 of the 16 original commits had one).
2. Every commit lost private material: a private project brief (one file), and the account-balance columns of two budget tables, in `docs/benchmark/plan.md` and `docs/benchmark/campaign-log.md`.
3. Two sentences about how the work was done were reworded, in `examples/benchmark-suite/README.md` and `docs/benchmark/plan.md`.

Nothing else changed. Each commit keeps its other files, its author, committer, dates and order, and its message apart from the trailer. Code, configs, tasks and benchmark evidence are byte-identical. Every commit ID changed, because an ID covers the message and the files.

Run records cannot be edited (their checksums would break), so each run's `manifest.json` still names the commit it ran from by its **old** ID, in `suite_commit`. This table maps each old ID to the commit as it is now.

| Old ID (in run records) | Current ID | Committed (UTC) | Subject | Runs recorded at this commit |
|---|---|---|---|---|
| `7310c4042ec0` | `9862da7be621` | 2026-09-26 23:48:25 | Vertical slice: Harbor-backed agent canary with sequential statistics | — |
| `0221fa39203a` | `027353388167` | 2026-09-26 23:48:25 | Power simulation, tunable e-process mixture bound, secret guard | — |
| `128b2e8a2329` | `9ba18ff0ed9b` | 2026-09-26 23:48:25 | Harness binary cache, infrastructure-error classification, spike fixes | — |
| `c2f8da555307` | `15f1e0a84e4f` | 2026-09-26 23:48:25 | Spike 0001 complete: Claude Code 2.1.283 end to end, first real A/B | — |
| `a00f706e60bc` | `7de58efbf9b7` | 2026-10-19 09:00:55 | Spending guardrails, verifier-lite, triggers, alerts, re-pricing, benchmark suite | `20261019T101312Z-run-02dbad`, `20261019T101509Z-run-86d625`, `20261019T101620Z-run-c1012e`, `20261019T101730Z-run-48b01a`, `20261019T101908Z-run-89299f`, `20261019T102031Z-run-1018c1`, `20261019T102146Z-run-208d83`, `20261019T110142Z-compare-99a38e`, `20261019T111053Z-run-d63e03`, `20261019T111911Z-run-06df76`, `20261019T112356Z-run-8f8864`, `20261020T172942Z-run-312890`, `20261020T172942Z-run-3c9b77` (uncommitted changes), `20261020T173356Z-run-8f24e9` (uncommitted changes) |
| `f81ed6919baf` | `852dba4aadb5` | 2026-10-20 17:46:38 | Benchmark steps 1-4 and the Codex spike: results, verifier reads Codex code mode, headline revised to 10 tasks | `20261020T174900Z-compare-98c8b5` |
| `8f900ad1cf18` | `7e55d31ea5a3` | 2026-10-20 19:45:30 | Continue a finished compare with more batches (--continue-from) | `20261020T194637Z-run-f2d77a`, `20261020T195046Z-compare-3053f5` |
| `c14e90841c42` | `95f3131be410` | 2026-10-20 20:14:36 | Benchmark steps 5 and 7: headline not flagged (E=11.3), pass rate 63% vs 45%; campaign log | `20261020T202808Z-compare-46fc4b`, `20261020T202808Z-compare-b725f2` |
| `6a7252bfb346` | `81212f9bbd9d` | 2026-10-20 21:17:50 | Benchmark campaign: caching-off check, Codex headroom check, reproducible report and README results | `20261021T020615Z-run-02a846` |
| `7a3cb1f336d0` | `2872e9e18049` | 2026-10-21 02:55:48 | Codex effort-none probe: 11/18 vs 18/18; agent timeout not enforced by Harbor for Codex | — |
| `52438713c7f0` | `6d7e9178897e` | 2026-10-21 03:00:46 | Pre-register the replicated Codex benchmark (5 detection runs, 2 A/A runs) | `20261021T030101Z-compare-b295f8`, `20261021T030122Z-compare-aae17d` |
| `31249532bf59` | `bda49a39cd14` | 2026-10-21 03:02:23 | Roadmap: v0.1 status after the October campaign | — |
| `e5f4e51c5444` | `345ad08f406b` | 2026-10-21 03:41:10 | Competitive re-check 2026-10-21 and README alternatives | `20261021T034602Z-compare-c037da`, `20261021T034624Z-compare-54eac1`, `20261021T041401Z-compare-b4d862`, `20261021T041457Z-compare-1f52c5`, `20261021T042719Z-compare-32ee06` |
| `10a71a44b608` | `52211dc884b8` | 2026-10-21 05:19:56 | Replicated Codex benchmark: 5/5 detected, 0/2 false alarms; verifier rules v3 | — |
| `28738c073f2b` | `93c14447703d` | 2026-10-21 09:35:53 | Competitive re-check: agentassay, and the PyPI agent-canary name is taken | — |
| `aa1fededd64f` | `c8255b20c14b` | 2026-10-21 09:53:03 | Rename the project to pinbench (ADR-0010) | — |

**The replicated Codex benchmark.** Its protocol was committed at 03:00:46 UTC (old ID `52438713c7f0`); the first of its runs started at 03:01:01 UTC. Two runs record that commit. The other five started after two documentation commits made while they ran (`31249532bf59`, `e5f4e51c5444`). Between `52438713c7f0` and `e5f4e51c5444` only `README.md`, `docs/roadmap.md` and a research note changed: code, configs and tasks are identical at both.

Runs marked "uncommitted changes" ran with edits not yet committed (`suite_dirty` in the manifest); for those the commit is the nearest committed state, not an exact one.

The table lists the runs whose records are committed under `benchmarks/results/campaign-2026-10/`. The original history, which the old IDs belong to, is kept privately by the owner. Earlier versions of this file listed IDs from an intermediate state of the same day's cleanup; this table supersedes them.
