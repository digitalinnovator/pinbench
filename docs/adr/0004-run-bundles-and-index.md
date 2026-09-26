# ADR-0004: Immutable run bundles are the system of record; SQLite is a rebuildable index

- Status: Accepted
- Date: 2026-09-27

## Context

A canary verdict such as "Claude Code 2.1.284 regressed pass rate, p ≤ 0.02" must be auditable weeks later. That means knowing exactly which task contents, harness version, model, options, Harbor version and statistics settings produced it, and being able to recompute it. Results also need to be queryable across runs, for listing, trends and the future efficiency index.

## Decision

1. **Each canary invocation writes one run bundle**, a directory under `.canary/runs/<run_id>/`:
   - `manifest.json`: canary version, Harbor version, suite name, git commit and dirty flag, a SHA-256 digest of every task directory, the full pin specs with their fingerprints, the statistics settings, budget and bootstrap seed.
   - `harbor/`: the raw Harbor job directories, untouched. These hold each trial's `result.json`, `lock.json`, agent logs, ATIF trajectory and verifier output.
   - `trials.jsonl`: one normalised `TrialRecord` per trial.
   - `verdict.json`: the statistical outcome and the reason for stopping (compare runs only).
   - `SHA256SUMS`: a checksum for every file above, written last.
2. **Sealing.** After `SHA256SUMS` is written, every file becomes read-only (`0444`) and every directory `0555`. `canary verify <run_id>` recomputes the checksums. Local files cannot be made truly immutable, so the guarantee is that tampering is evident, not prevented.
3. **Pin fingerprint.** A pin's fingerprint is a SHA-256 over its canonical JSON: harness, version, model, options, environment variable *names*, and the content hashes of any referenced config files. Values of secret-bearing variables are never recorded. The same fingerprint means the same configuration.
4. **SQLite (`.canary/index.db`) is a derived index**, rebuilt from bundles by `canary index rebuild`. The bundles are authoritative. The index can be deleted at any time.
5. **Reports are derived artefacts outside the bundle** (`.canary/reports/<run_id>.html`). They link into the bundle for trace drill-down, so a template change never alters a sealed bundle.

## Consequences

- Any verdict can be recomputed from its bundle alone. That is also how the benchmark's published numbers become reproducible.
- Bundles are large, because the Harbor trial directories include transcripts. Retention and compression are on the roadmap. Nothing is deleted automatically.
- The index schema can change freely. Migration means rebuilding.
- Secret *names* appear in manifests and secret values do not. Harbor already redacts sensitive environment values in its own `config.json`, and we rely on that for the raw trial directories as well.

## Alternatives considered

- **Database as the source of truth.** Easier to query, but verdicts would depend on a mutable store, and exporting a self-contained, shareable run would take extra work.
- **Content-addressed object store (CAS) for trial files.** It deduplicates better, but it is more machinery than v0.1 needs. The bundle layout does not preclude adding it later.
- **Rendering reports inside the bundle.** Improving the report template would then either mutate sealed bundles or leave stale reports inside them.
