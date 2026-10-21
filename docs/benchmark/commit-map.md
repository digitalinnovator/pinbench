# Commit IDs before and after the 2026-10-21 message cleanup

On 2026-10-21 every commit message in this repository was edited to remove an attribution trailer. Nothing else changed: each commit keeps its files (the same tree ID), author, committer, dates and order. But a commit's ID covers its message, so every ID changed.

Run records cannot be edited (their checksums would break), so each run's `manifest.json` still names the commit it ran from by its **old** ID, in `suite_commit`. Use this table to find the commit as it is now. The tree ID is the same before and after, so `git cat-file -p <new ID>` shows the tree the run recorded.

| Old ID (in run records) | Current ID | Tree | Committed (UTC) | Subject | Runs recorded at this commit |
|---|---|---|---|---|---|
| `7310c4042ec0` | `c14f5ffba5a5` | `824adee05fbb` | 2026-09-26 23:48:25 | Vertical slice: Harbor-backed agent canary with sequential statistics | — |
| `0221fa39203a` | `7276f45e45f1` | `c69ba9d557f4` | 2026-09-26 23:48:25 | Power simulation, tunable e-process mixture bound, secret guard | — |
| `128b2e8a2329` | `95d3726edd86` | `20af733c7c80` | 2026-09-26 23:48:25 | Harness binary cache, infrastructure-error classification, spike fixes | — |
| `c2f8da555307` | `46afbdb15b63` | `7255771211bf` | 2026-09-26 23:48:25 | Spike 0001 complete: Claude Code 2.1.283 end to end, first real A/B | — |
| `a00f706e60bc` | `cef6736e9e3d` | `361794e0ce9e` | 2026-10-19 09:00:55 | Spending guardrails, verifier-lite, triggers, alerts, re-pricing, benchmark suite | `20261019T101312Z-run-02dbad`, `20261019T101509Z-run-86d625`, `20261019T101620Z-run-c1012e`, `20261019T101730Z-run-48b01a`, `20261019T101908Z-run-89299f`, `20261019T102031Z-run-1018c1`, `20261019T102146Z-run-208d83`, `20261019T110142Z-compare-99a38e`, `20261019T111053Z-run-d63e03`, `20261019T111911Z-run-06df76`, `20261019T112356Z-run-8f8864`, `20261020T172942Z-run-312890`, `20261020T172942Z-run-3c9b77` (uncommitted changes), `20261020T173356Z-run-8f24e9` (uncommitted changes) |
| `f81ed6919baf` | `77baff93c21f` | `d6f187958e7b` | 2026-10-20 17:46:38 | Benchmark steps 1-4 and the Codex spike: results, verifier reads Codex code mode, headline revised to 10 tasks | `20261020T174900Z-compare-98c8b5` |
| `8f900ad1cf18` | `bc71a0713696` | `d60fee7550e2` | 2026-10-20 19:45:30 | Continue a finished compare with more batches (--continue-from) | `20261020T194637Z-run-f2d77a`, `20261020T195046Z-compare-3053f5` |
| `c14e90841c42` | `916d5d250483` | `ef396a547735` | 2026-10-20 20:14:36 | Benchmark steps 5 and 7: headline not flagged (E=11.3), pass rate 63% vs 45%; campaign log | `20261020T202808Z-compare-46fc4b`, `20261020T202808Z-compare-b725f2` |
| `6a7252bfb346` | `cd7b67caec0e` | `64a7f41878c6` | 2026-10-20 21:17:50 | Benchmark campaign: caching-off check, Codex headroom check, reproducible report and README results | `20261021T020615Z-run-02a846` |
| `7a3cb1f336d0` | `be60a26d4fed` | `ebaef1484af7` | 2026-10-21 02:55:48 | Codex effort-none probe: 11/18 vs 18/18; agent timeout not enforced by Harbor for Codex | — |
| `52438713c7f0` | `3fa8dedf958f` | `9f9c3439000f` | 2026-10-21 03:00:46 | Pre-register the replicated Codex benchmark (5 detection runs, 2 A/A runs) | `20261021T030101Z-compare-b295f8`, `20261021T030122Z-compare-aae17d` |
| `31249532bf59` | `a04552a4b22e` | `410b0265fa94` | 2026-10-21 03:02:23 | Roadmap: v0.1 status after the October campaign | — |
| `e5f4e51c5444` | `7f3e59a6515f` | `da0d44c9041a` | 2026-10-21 03:41:10 | Competitive re-check 2026-10-21 and README alternatives | `20261021T034602Z-compare-c037da`, `20261021T034624Z-compare-54eac1`, `20261021T041401Z-compare-b4d862`, `20261021T041457Z-compare-1f52c5`, `20261021T042719Z-compare-32ee06` |
| `10a71a44b608` | `936b835b3514` | `cd8243a4f17b` | 2026-10-21 05:19:56 | Replicated Codex benchmark: 5/5 detected, 0/2 false alarms; verifier rules v3 | — |
| `28738c073f2b` | `6c0077428817` | `e3766714a9f0` | 2026-10-21 09:35:53 | Competitive re-check: agentassay, and the PyPI agent-canary name is taken | — |
| `aa1fededd64f` | `df45b56b9b30` | `4a6906525e26` | 2026-10-21 09:53:03 | Rename the project to pinbench (ADR-0010) | — |

**The replicated Codex benchmark.** Its protocol was committed at 03:00:46 UTC (old ID `52438713c7f0`); the first of its runs started at 03:01:01 UTC. Two runs record that commit. The other five started after two documentation commits made while they ran (`31249532bf59`, `e5f4e51c5444`). Between `52438713c7f0` and `e5f4e51c5444` only `README.md`, `docs/roadmap.md` and a research note changed: code, configs and tasks are identical at both.

Runs marked "uncommitted changes" ran with edits not yet committed (`suite_dirty` in the manifest); for those the commit is the nearest committed state, not an exact one.

The table lists the runs whose records are committed under `benchmarks/results/campaign-2026-10/`. The original history is kept on the owner's machine.
