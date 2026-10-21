# ADR-0005: Re-price cost from token counts with a pinned price table

- Status: Accepted (2026-09-30; proposed 2026-09-27)
- Evidence: [spike 0001, section 4](../spikes/0001-harbor-claude-code.md)

## Context

pinbench compares dollars per task across harness versions. None of the three harnesses report billed cost. They estimate it on the client:

- Claude Code computes `total_cost_usd` from a price table **bundled into each build**.
- Codex reports no cost in its JSON stream. Harbor estimates it with LiteLLM's price table.
- OpenCode prices from a catalogue **fetched at runtime** from models.dev.

So a harness upgrade that only changes the bundled price table would appear as a cost regression, or hide one. Replaying March–April 2026 Claude Code builds would report cost at those builds' prices. Token counts are what the harness actually consumed, and they are comparable across versions.

Two findings from the real trials sharpen this:

- **The cost Harbor reported for Claude Code 2.1.283 was itself a LiteLLM estimate.** Every request in the transcripts is tagged `cost_source: "litellm_estimate"`. The "harness-reported" number therefore depends on the LiteLLM version pinned in Harbor's environment.
- **Prompt-cache state moves cost more than the harness setting did.** The first trials of a configuration wrote about 16,000 tokens to the prompt cache and read none; later trials of the same configuration wrote none and read them back. On a small task that is the difference between $0.13 and $0.03 (spike 0001, section 4).

## Decision

1. **Record each harness's reported cost as `reported_cost_usd`.** It is kept, but it is not the comparison metric.
2. **Compute `cost_usd` from token usage and a price table versioned in this repository** (`src/pinbench/data/prices.toml`). The table is dated, names its source page, and is checked for internal consistency by a test. Every run bundle's manifest records the table's version and SHA-256.
3. **Usage comes from the transcript, per request.** The ATIF trajectory gives, for each model request: prompt tokens, cache reads, cache writes split by 5-minute and 1-hour TTL, output tokens, the model, speed and inference geography. Each category is priced separately. Harbor's `result.json` totals cannot be used: they do not separate cache writes from uncached input.
4. **Never part-price a trial.** An unknown model, fast mode or a transcript with no usage leaves the trial's `cost_usd` empty. If any scored trial in a comparison is un-priced, the cost metric falls back to `reported_cost_usd` for both arms and is labelled as such. Both arms are always priced the same way.
5. **Budget enforcement uses the higher of the two estimates per trial**, so a stale table can never let pinbench overspend.
6. **Cache reads and writes are reported as their own metrics** (`cache_read_tokens`, `cache_write_tokens`), next to cost. A cost ratio should be read together with them.
7. **`[stats] warmup_batches`** leaves the first N batches out of the cost, token and latency comparison. They still count for pass rate and for the budget, so nothing is wasted. The default is 0. Small suites should set 1.

## Consequences

- Cost comparisons across harness versions measure consumption, not price-table drift.
- **Verified on real data:** on all 15 scored Claude Code trials from spike 0001, `cost_usd` equals the reported cost to within floating-point rounding. That validates the token accounting and the Opus 5 prices. It also means re-pricing changes no number yet; its value appears when the two arms are different harness builds.
- The table covers Anthropic models at first-party API prices only. Codex and OpenCode trials on other providers stay on reported cost until their prices are added with the same verification. Bedrock, Vertex AI, fast mode and the Batch API are not covered.
- The price table must be maintained. A model missing from it degrades the comparison to reported cost, visibly; it does not fail the run.
- A warm-up batch cannot remove cache effects entirely. With `n_concurrent` trials starting together, the first few trials of each arm in each new cache window are cold. On a suite of 25 or more tasks that is a small share of a batch. Prompt caches also expire after five idle minutes, so a long gap between batches makes the next batch cold again for both arms.
- **Cache writes are signal as well as noise.** A harness caching bug (the postmortem's March 26 regression) shows up as *persistently* more cache writes and fewer reads. That is why cache state is reported and not normalised away.
- ATIF token semantics are confirmed for Harbor's Claude Code adapter only (prompt tokens include cache reads and writes). The Codex and OpenCode adapters need the same check in their spikes.

## Alternatives considered

- **Trust harness-reported cost.** Simple, and wrong across versions.
- **LiteLLM's price table.** It is in Harbor's environment, but it is a large dependency with its own update cadence, and it was the supply-chain incident vector in March 2026. A small table we own is auditable.
- **Billing APIs (for example, Anthropic's Usage and Cost Admin API).** Billed truth, but it needs admin credentials and attributes cost per API key, not per trial. It is good for reconciliation, not per-trial attribution.
- **A cache-neutral cost** (price every prompt token as if uncached, or as if cached). It removes warm-up noise, but it also hides the caching regressions pinbench exists to catch.
- **A discarded warm-up batch.** It pays for trials and throws them away. Keeping the batch for pass rate and dropping it only from cost metrics gets the same correction for free.
