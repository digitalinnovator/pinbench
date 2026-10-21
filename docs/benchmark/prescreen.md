# Free pre-screen of the benchmark tasks

> The project was renamed from "agent canary" to **pinbench** on 2026-10-21 ([ADR-0010](../adr/0010-name-pinbench.md)). This record keeps the names used at the time: `canary` is now `pinbench`, and `canary.toml` is `pinbench.toml`.

Before any API credit is spent, every candidate task is solved blind by Claude Sonnet 5 at two reasoning-effort settings, and the attempts are scored by the task's hidden tests. The pre-screen costs no API credit: the attempts run as Claude Code subagents on the owner's subscription.

**What it is good for:** finding tasks with no headroom (every attempt passes, or none does) and the direction of the effort effect, before paying for calibration.

**What it is not:** a measurement of the canary's benchmark. The solver is a Claude Code subagent given the task text, not Claude Code launched by Harbor in a sandbox. The model and the effort parameter are the same; the system prompt, the tools and the working environment are not. Pass rates here will not equal pass rates in the paid runs.

## Protocol

- **Solver:** `claude-sonnet-5`, reasoning effort `high` or `low`, four attempts per task per effort, all interleaved so both arms run over the same period.
- **Input:** a copy of the task's `environment/app` and its `instruction.md`, nothing else. The solver is told to work only in its copy and not to look for tests or solutions.
- **Scoring:** the task's own hidden tests (`tests/test_solution.py`), run against each copy afterwards. All-or-nothing, as in the benchmark.
- **Contamination check:** every tool call in every attempt's transcript is searched for paths into the suite's tests, solutions and naive scripts.

## Round 1, 2026-09-30: the suite as first written

256 attempts. No attempt read a hidden test or a solution.

| | High effort | Low effort |
|---|---|---|
| Attempts passed (of 128) | 118 (92%) | 104 (81%) |
| Tool calls per attempt, median | 7 | 5 |
| Output per attempt, relative | 1 | about 0.34 |

- The effort setting changed behaviour. Low effort wrote about a third of the output, close to the 0.36× measured on Opus 5 in the real harness (spike 0001).
- **22 of 32 tasks were passed 8 times out of 8.** They carry no signal.
- Eight tasks separated the arms: `env-file-parser` (4/4 against 1/4), `version-range-match` (3/4 against 0/4), `time-range-parse` (3/4 against 1/4), `cli-grep-lite` (4/4 against 2/4), and one attempt each on `dedupe-contacts`, `invoice-rounding`, `priority-queue-stable` and `strip-comments`. `cli-short-flags` went the other way (3/4 against 4/4).
- Two tasks were passed almost never: `format-number` (0/8) and `title-case-style` (1/8).
- **What low effort missed** was the same kind of thing each time: a rule the instruction states, that the obvious quick implementation breaks, and that trying one's own edge cases would expose. Examples: only spaces allowed around a separator (a quick solution used `\s` and `strip()`), no leading zeros in numeric identifiers, a line ending only at `\n` (`str.splitlines()` breaks on other characters), an all-or-nothing update, and rounding per line in every function that reports tax.

**Action taken:** the 22 saturated tasks were given one to three more rules of that kind, and the two near-impossible tasks were eased. Each revision was confirmed against the round-1 attempts (most had to fail the new hidden tests), then reviewed: the reviewer solved the task quickly and then carefully before reading the hidden tests, and checked every hidden assertion against the instruction. All 32 tasks still pass `make check-suite`.

## Round 2, 2026-10-18: the retuned suite

256 fresh attempts. No attempt read a hidden test or a solution. Low effort again made fewer tool calls (median 5 against 7) and wrote about 40% of the output.

| | High effort | Low effort |
|---|---|---|
| Attempts passed (of 128) | 85 (66%) | 51 (40%) |

| Task | High | Low | | Task | High | Low |
|---|---|---|---|---|---|---|
| business-days | 2/4 | 3/4 | | lru-ttl-cache | 4/4 | 4/4 |
| cli-config-precedence | 4/4 | 4/4 | | money-split | 3/4 | 1/4 |
| cli-grep-lite | 4/4 | 3/4 | | monthly-recurrence | 0/4 | 0/4 |
| cli-short-flags | 4/4 | 1/4 | | order-state-machine | 4/4 | 1/4 |
| coin-change-limited | 4/4 | 3/4 | | pagination-cursor | 0/4 | 0/4 |
| dedupe-contacts | 4/4 | 2/4 | | path-normalize | 2/4 | 1/4 |
| dependency-order | 4/4 | 3/4 | | priority-queue-stable | 2/4 | 2/4 |
| env-file-parser | 4/4 | 3/4 | | query-canonicalize | 3/4 | 3/4 |
| extract-registry-class | 2/4 | 1/4 | | range-list | 0/4 | 0/4 |
| format-number | 2/4 | 0/4 | | split-toplevel | 4/4 | 4/4 |
| glob-match | 4/4 | 0/4 | | strip-comments | 4/4 | 3/4 |
| human-bytes | 0/4 | 0/4 | | time-range-parse | 1/4 | 0/4 |
| interval-set | 2/4 | 1/4 | | title-case-style | 3/4 | 2/4 |
| invoice-rounding | 4/4 | 1/4 | | unify-money-format | 1/4 | 1/4 |
| iso-week-report | 2/4 | 0/4 | | version-range-match | 4/4 | 1/4 |
| log-window-count | 0/4 | 0/4 | | wrap-quoted | 4/4 | 3/4 |

- **The retune worked, and overshot in places.** The gap between the arms grew from 11 points to 27. Three tasks are still passed by every attempt, and five are now passed by none.
- **What separates the arms is varied.** Of the hidden cases that low effort failed more often than high effort, about three quarters test task-specific behaviour: an all-or-nothing rename, tax rounded per line in every function, case-insensitive matching of non-ASCII letters, exact long decimals, cursor validation. About a quarter are whitespace or newline rules. Unicode-digit rules appear in several tasks but separate the arms almost nowhere; they are mostly failed by both.
- **The five tasks nobody passed** each fail on input-validation rules (a trailing newline, a non-ASCII digit, a cursor that is not a string) at both efforts. They carry no signal as they stand and are left out. Easing them is on the roadmap.

## Selection for the benchmark (fixed before any paid trial)

The rule, applied mechanically to round 2:

1. Leave out every task on which all 8 attempts agreed (8 of 8 passed, or 0 of 8).
2. Leave out every task whose high-effort arm passed at most 1 of 4: there is no room for a drop.
3. Rank the rest by high-effort passes minus low-effort passes, then by high-effort passes, then by name, and keep the first 18.

Selected: `glob-match`, `cli-short-flags`, `invoice-rounding`, `order-state-machine`, `version-range-match`, `dedupe-contacts`, `money-split`, `format-number`, `iso-week-report`, `cli-grep-lite`, `coin-change-limited`, `dependency-order`, `env-file-parser`, `strip-comments`, `wrap-quoted`, `title-case-style`, `extract-registry-class`, `interval-set`.

Ranked out: `path-normalize`, `query-canonicalize`, `priority-queue-stable`, `business-days`.

**Is selecting on both arms legitimate?** Yes, because the benchmark's test runs on fresh paid trials, never on these attempts. What selection does bias is the *expected* effect: tasks chosen for a large gap here will tend to show a smaller one in fresh trials (regression to the mean), and the real harness differs from the subagent. The power estimates below allow for both.

## What this predicts for the headline run (simulated)

The headline compares effort high against low on the 18 tasks, at most 5 batches, with the futility look after batch 3 (plan, step 5). Simulated with the shipped e-process, 20,000 runs per row:

| Assumed per-task pass rates | Mean drop | Detection | Mean trials |
|---|---|---|---|
| Round 2 as measured | 46 points | 100% | 63 |
| Shrunk toward 50% (Beta(1, 1) prior on each arm) | 31 points | 96% | 101 |
| Shrunk, then half the effect, for a weaker transfer to the real harness | 15 points | 38% | 150 |

The middle row is the planning case. The last row is the pessimistic one: the real harness under Harbor could show a much smaller effect than the subagent did. The futility look stops such a run after three batches if it is going nowhere.
