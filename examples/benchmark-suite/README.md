# Benchmark suite: candidate tasks

Thirty-two small Python tasks in Harbor's task format, written for the regression-injection benchmark ([plan](../../docs/benchmark/plan.md)). They are **candidates**: calibration decides which ones the benchmark uses, and `canary.toml`'s `[suite] include` list records that choice.

## What a task is for

A canary needs tasks a strong agent passes most of the time but not always, and less often when it is careless. Each task therefore has many easy rules and one to three rules that a careful reader gets right and a hurried one gets wrong. The reward is all-or-nothing: every hidden test must pass.

## Layout

```text
tasks/<slug>/
  task.toml                 Harbor task config
  instruction.md            the whole prompt the agent gets
  environment/Dockerfile    identical in every task, so Docker builds the heavy layers once
  environment/app/          starting code and one small visible test
  solution/solve.sh         reference solution (what Harbor's zero-cost oracle agent applies)
  tests/                    hidden tests; Harbor copies them in only after the agent finishes
naive/<slug>.sh             a plausible careless solution: passes the visible test, fails hidden ones
```

The `naive/` scripts are not part of any task. They document the trap each task sets and let the checker prove it is real.

## Fairness rules

- Every hidden assertion follows from a sentence in `instruction.md`.
- The instruction states each rule once, in neutral wording, with no worked example of the trap case and no warning.
- No test depends on exact error text, float representation, timing, or behaviour the instruction does not state.
- The visible test is correct, small, and passes on the careless solution.

Each task was written by one agent, then attacked by a second that solved it blind from the instruction alone before reading the tests, and checked every hidden assertion against the instruction. No unfair assertion was found in the 32 tasks; 28 were judged too easy for a top model and were given one more stated rule.

## Check the tasks

```bash
make check-suite     # no Docker, no harness, no API calls
```

For each task this proves that the hidden tests fail on the starting code, pass on the reference solution, and fail on the careless solution while the visible test passes on it. CI runs it on every push.

## Provenance and licence

The tasks were written from scratch for this repository and are Apache-2.0, like the rest of it. They use common problem shapes with original specifications; no third-party problem statements or tests were copied. They were drafted with AI assistance and reviewed as described above.
