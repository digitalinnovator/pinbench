# Benchmark plan: regression-injection detection power

The benchmark is the launch (see the portfolio principles). This plan fixes the protocol before any money is spent, so the published numbers cannot be tuned after the fact.

## Question

For each harness-layer regression type from Anthropic's 2026-04-23 postmortem, how many runs and dollars does the canary need to flag it at 95% confidence, on a realistic private-style suite?

## Arms

All arms use one harness version and one model, and change exactly one thing. The pins are in `examples/demo-suite/canary.toml` and will move to the benchmark suite's config.

| Arm | Change | Postmortem analogue |
|---|---|---|
| `cc-baseline` | Claude Code at a pinned version, `reasoning_effort = "high"` | — |
| `cc-low-effort` | `reasoning_effort = "low"` | Default effort lowered (Mar 4) |
| `cc-verbose` | `append_system_prompt` demanding terse output | Verbosity system-prompt change (Apr 16) |
| `cc-no-cache` | `DISABLE_PROMPT_CACHING=1` | Thinking-block caching bug (Mar 26), approximated |
| `cc-baseline` (A/A) | Identical to baseline | Measured false-alarm rate |

`cc-no-cache` is expected to move cost and latency, not pass rate. It exercises the bootstrap side, not the e-process.

## Suite

The [power simulation](../../benchmarks/results/power-simulation.md) says suite size dominates:

- **10 tasks:** a 10-point drop is caught about 47% of the time within 20 batches.
- **25 tasks:** about 86%.
- **50 tasks:** about 99%.

Tasks that always pass or always fail carry no evidence. Requirements:

- **25–50 tasks** whose baseline pass rate falls between 20% and 90% under `cc-baseline`. Measure this in a calibration pass (below) and drop the rest.
- **Sources, in order of preference:**
  1. a Terminal-Bench 2 subset from Harbor's registry (public, already in Harbor's format);
  2. SWE-bench-style tasks from permissively licensed repos;
  3. hand-written tasks like `examples/demo-suite`.

  Record every task's licence.
- **Contamination note.** Public tasks may be in training data. That affects absolute pass rates, not the *difference* between arms, which is what the benchmark measures.
- **Disk budget.** Terminal-Bench images can be large. Check free space first; the dev machine is tight.

## Protocol

1. **Calibration** (not published). Run `cc-baseline` with 2 attempts per task to measure per-task pass rates and cost per trial. Replace the simulation's $0.50 placeholder with the measured median, and re-run `make power` with the measured pass-rate spread.
2. **Pre-register.** Commit the suite, the pins, α = 0.05, mixture bound 0.8, the batch cap and the dollar cap before the measured runs.
3. **Measured runs.** Run `canary compare cc-baseline <arm>` R times per arm with different seeds. R ≥ 5 gives a spread; the budget decides the final R. Every run produces a sealed bundle.
4. **Report**, per arm:
   - detection rate across the R runs
   - median batches and dollars to detection
   - cost, token and latency ratios with their intervals
   - the A/A false-alarm count

   Also include the fixed-N McNemar decision on the same trials. It is computable from the bundles, needs no extra spend, and is what a fixed-sample tool would have concluded.
5. **Publish.** A script under `benchmarks/` regenerates every number in the README from the committed bundles' `verdict.json` files.

## Budget (to confirm after calibration)

At the placeholder $0.50 per trial, with 25 tasks:

- One compare run averages about $266 for a 10-point drop and up to $500 at the 20-batch cap.
- Four arms × R = 5 comes to roughly $5k–10k.

That is too much for a first publication. Options:

- a cheaper model tier for the published run, keeping one Opus-tier confirmation;
- fewer arms (effort and verbosity first);
- R = 3.

The owner decides once calibration gives the real cost per trial.

## Out of scope for the first publication

- Codex and OpenCode arms. The same protocol applies once each has its own adapter spike.
- The old-build replay of the real March–April timeline. It needs the "old builds still behave consistently against today's API" check first.
