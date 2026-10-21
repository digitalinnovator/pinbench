# ADR-0009: A campaign ledger bounds spending; `max_usd` only steers a run

- Status: Accepted
- Date: 2026-09-30
- Evidence: a spending-path audit and a four-lens adversarial review, both run on 2026-09-30 with no API spend. The review confirmed 28 findings against the first version of this design; the decision below includes their fixes.

## Context

The brief requires "budget caps per pinbench run, so pinbench can't run up a bill". The first implementation had one rule: before each batch after the first, stop if spend plus the average batch cost would pass `[budget] max_usd`. An audit showed that this is not a bound:

- The first batch ran before any check. With the demo config it could cost about $10 against a $5 `max_usd`.
- One trial with no reported cost switched the check off for the rest of the run.
- `pinbench run` had no dollar check at all.
- Nothing connected one invocation to the next. A second run, a scheduled `pinbench watch`, or two runs at once each had a fresh budget.
- An empty API account produced trials that scored as agent failures, so the run kept going and could report a regression.

The operator's whole budget can be a few tens of dollars. The tool has to make an overspend impossible by construction, not unlikely by estimate.

## Decision

1. **Two bounds with different jobs.**
   - `[budget] max_usd` stays a *soft* stop for one compare run, computed from measured spend. It decides when a run has cost enough.
   - A **campaign ledger** is the *hard* bound. It holds a lifetime limit per credit pool (for example `anthropic`, `openai`) across every run on the machine.
2. **Reserve the worst case, then settle.** Before every batch that can spend, including the first batch and every `pinbench run`, pinbench reserves trials × per-trial cap against the pool's limit and refuses to start if that does not fit. After the batch it replaces the reservation with what the batch cost.
3. **A cap counts only if something enforces it.**
   - Claude Code: `options.max_budget_usd` is required. The reservation is that cap plus an allowance for the request in flight when the cap is crossed: the larger of `[budget] inflight_allowance_usd` and one typical request at the model's prices (20k tokens written to a cold cache plus 4k output tokens).
   - A harness with no dollar cap (Codex, OpenCode): both `timeout_sec` and `reserve_usd` are required. The timeout is what stops the trial; `reserve_usd` is the operator's estimate of what a trial running to the timeout can cost.
   - `reserve_usd` can raise a reservation and can never lower one. `max_budget_usd` on a harness that has no such flag is a config error.
   - A paid pin with no enforced bound is refused before anything is created.
4. **Fail closed on unknown cost.** A trial with no cost, a trial missing from the batch's output, and a batch that crashes are all charged at the cap. A batch that provably never started (the runner reports so before launching anything) is released.
5. **One ledger per machine, not per suite.** It lives outside every suite's `.pinbench`, in `$XDG_STATE_HOME/pinbench/ledger`, or where `PINBENCH_LEDGER_DIR` points. It is not configurable in `pinbench.toml`: a ledger per suite would be a limit per suite and no limit overall.
6. **The ledger is an append-only JSON-lines file per pool, written under a file lock.** A line that cannot be parsed, or an amount that is not a finite number, stops spending until a person fixes the file. It never reads as zero.
7. **Operator commands are explicit and narrow.**
   - `pinbench ledger limit <pool> <usd>` sets the limit. `--if-unset` makes it safe in a scheduled job.
   - `pinbench ledger status` shows spend, held reservations with their run ids, and what is left.
   - `pinbench ledger correct <pool> --add|--remove <usd> --note …` reconciles with the provider's console.
   - `pinbench ledger release <pool> --run-id … --actual-usd … --note …` settles the reservations of one crashed run. It refuses a reservation younger than four hours unless forced, because a batch that is still running keeps spending.
8. **Stop paying for nothing.**
   - *Dead batch:* a batch with no usable pair, or with one arm all infrastructure errors, ends the run with no verdict and exit code 2. "Credit balance is too low" from the harness is an infrastructure error, matched only as the harness's whole error message.
   - *Futility (optional):* one pre-registered look after N batches stops the run unless the candidate is behind by a set margin. It can only end a run as inconclusive, so it cannot raise the false-alarm rate of an anytime-valid test.
   - *Retries:* the Harbor job config pins `retry.max_retries = 0`, and the job lock is checked for it.
9. **See the bill first.** `--dry-run` on `run`, `compare` and `watch` prints trials per batch, the per-trial caps, the worst case, what the ledger has left, and whether the run would be refused.
10. **One batch must fit `max_usd`.** A paid run is refused if a single batch at its caps could cost more than `max_usd`.
11. **Multi-step Harbor tasks are refused.** Each step runs the harness again with a fresh cap, which one per-trial cap does not bound.

## Consequences

- **The guarantee.** For any sequence of invocations on one machine, settled spend plus held reservations never passes a pool's limit at the moment a batch starts. Real spend can exceed the limit only by what trials in the last batch overshoot beyond their allowance.
- **The allowance is an estimate, not a bound.** Claude Code checks its cap between messages, and one request can be larger than the allowance. Set the limit below the account balance by a margin, and keep a provider-side spend limit where the console offers one.
- **Reservations are deliberately pessimistic.** With caps a few times the expected trial cost, the ledger stops a run earlier than measured spend would. Tight, realistic caps buy more batches. A cap that binds in one arm more than the other is itself a treatment, so the report counts cap hits per arm.
- **A cap hit is scored like any other trial:** by the hidden tests, on whatever was finished. If Harbor's text patterns took something in a capped trial's output for an infrastructure error, pinbench scores it by reward anyway, because the harness's own result explains the exit.
- **`spent_usd` in a verdict is an upper bound when `cost_known` is false.** It includes trials charged at their cap. Benchmark figures such as "dollars to flag" must use measured trial costs.
- **An interrupt leaves a reservation held.** That is correct, and it needs a person: check that the run's processes and containers are gone, read the console, then `pinbench ledger release`.
- **The ledger cannot see spend it did not start:** another tool on the same API key, or a run on another machine. Reconcile against the console after every campaign step.
- **Scheduled jobs must persist the ledger.** The CI example caches it and sets the limit only if none exists. If the cache is lost, the limit starts again from zero.
- **Codex and OpenCode remain weakly bounded.** A timeout bounds time, not dollars; `reserve_usd` is a judgement. Run them one trial at a time until a real cost per trial is known.
- Free harnesses (`oracle`, `nop`) and the simulated runner never touch the ledger.

## Alternatives considered

- **Make `max_usd` hard by pricing every batch at its caps.** One number, but caps are several times real cost, so a run would stop after one or two batches. Measured spend is the right signal for "this run has cost enough"; worst-case reservation is the right signal for "this can never exceed the account".
- **A ledger per suite (`[budget] ledger_dir`).** Built and removed after review: it makes the lifetime limit a per-suite limit and lets the ledger commands and the run look at different files.
- **Trust the provider's spend limit alone.** It is the real backstop where it exists, but it is not available on every plan, it does not know which run spent what, and an exhausted account looks like a failing agent unless the tool detects it.
- **Charge unknown costs at zero and warn.** That was the original behaviour. A batch of failed-but-billed trials then counted as free.
- **A database for the ledger.** A file of JSON lines with a lock is enough for one machine, can be read and repaired by hand, and has no schema to migrate.
