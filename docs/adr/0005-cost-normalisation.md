# ADR-0005: Re-price cost from token counts with a pinned price table

- Status: Proposed. It must be accepted before any cost number is published.
- Date: 2026-09-27

## Context

The canary compares dollars per task across harness versions. None of the three harnesses report billed cost. They estimate it on the client:

- Claude Code computes `total_cost_usd` from a price table **bundled into each build**.
- Codex reports no cost in its JSON stream. Harbor estimates it with LiteLLM's price table.
- OpenCode prices from a catalogue **fetched at runtime** from models.dev.

So a harness upgrade that only changes the bundled price table would appear as a cost regression, or hide one. Replaying March–April 2026 Claude Code builds would report cost at those builds' prices. Token counts are what the harness actually consumed, and they are comparable across versions.

Spike 0001 adds a second reason. Server-side prompt caching makes a trial's cost depend on whether the same configuration ran recently: a cold arm pays cache writes and a warm arm pays cheap cache reads. Cost normalisation therefore needs to report cache reads and writes separately, and possibly discard a warm-up batch.

## Decision (proposed)

- Record each harness's reported cost as `reported_cost_usd`. It is kept, but it is not the comparison metric.
- Compute `cost_usd` = Σ over models of (input, cache-write, cache-read, output tokens × price) from a **price table versioned in this repository**, tagged with the date it was verified against the providers' pricing pages. Record the table's version in every run bundle.
- Budget enforcement uses whichever of the two estimates is higher, so a stale table can never let the canary overspend.
- Until this is implemented, reports label cost as "harness-reported" and warn when the two pins differ in harness version.

## Consequences

- Cost comparisons across harness versions measure consumption, not price-table drift.
- The price table must be maintained. The monthly efficiency index already needs a dated price basis.
- Token accounting differs per harness: cumulative versus per-step counts, and whether subagents are included. The per-harness token parsers need contract tests.

## Alternatives considered

- **Trust harness-reported cost.** Simple, and wrong across versions.
- **LiteLLM's price table.** It is in Harbor's environment, but it is a large dependency with its own update cadence, and it was the supply-chain incident vector in March 2026. A small table we own is auditable.
- **Billing APIs (for example, Anthropic's Usage and Cost Admin API).** Billed truth, but it needs admin credentials and attributes cost per API key, not per trial. It is good for reconciliation, not per-trial attribution.
