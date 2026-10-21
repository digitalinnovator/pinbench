# ADR-0006: Cache pinned harness binaries on the host and mount them into sandboxes

- Status: Accepted
- Date: 2026-09-27
- Evidence: [spike 0001, section 3a](../spikes/0001-harbor-claude-code.md)

## Context

By default, Harbor installs the harness inside every sandbox, on every trial. For Claude Code, the native installer downloads the `latest` binary (241.6 MB for linux-x64 at 2.1.283), verifies it, and then runs `claude install <version>`, which downloads the pinned version again. On the development machine's link (about 1.1 MB/s, measured on the host and inside Docker), three concurrent trials needed about 1.4 GB. That is roughly 22 minutes, and every trial failed Harbor's agent-setup timeout, at both 360 s and 720 s.

Beyond speed, per-trial installs are a reproducibility and supply-chain concern. Every trial re-fetches vendor code over the network, and nothing records which bytes actually ran.

## Decision

- **Download once per version.** pinbench downloads each pinned Claude Code binary once, into a host cache (`$XDG_CACHE_HOME/pinbench/harness/claude-code/<version>/<platform>/claude`).
- **Verify against the release manifest.** The download's SHA-256 must match `downloads.claude.ai/claude-code-releases/<version>/manifest.json`. On a mismatch pinbench refuses to use the file.
- **Mount read-only.** Each batch bind-mounts the binary read-only at `/usr/local/bin/claude`. Harbor's install check then sees `claude --version` equal to the pin and skips its own install.
- **Record provenance.** Each batch writes `harbor-configs/batch-NNN.harness.json` (version, platform, SHA-256, source URL) into the run bundle. The sealed bundle therefore records exactly which harness bytes ran.
- **Scope.** Claude Code only, on glibc Linux images (`[runner] harness_cache = true`, the default).
- **One job per version (amended 2026-09-30).** Harbor mounts are job-wide, so a batch whose pins use different Claude Code versions is split into one Harbor job per version. Each job mounts its own binary. The jobs start together and share the batch's concurrency budget (`n_concurrent` divided by the number of jobs), so both arms still run in the same time window with the same total API load. Pins that share a version stay in one job, as before.

## Consequences

- Setup drops from a network-bound multi-minute install to a mount. Trials measure the agent, not the downloader.
- Every trial of a pin runs byte-identical harness code, verified against the vendor manifest.
- Comparing two Claude Code *versions* no longer pays the in-sandbox install. The cost is that each task image is built once per job (cheap with a warm Docker layer cache) and that the two arms are separate Harbor processes. The split is covered by tests against a fake Harbor CLI; **a real two-version run has not been made yet.**
- Version-specific mount paths with a per-agent PATH would keep one job, but Harbor's install check looks for `claude` on the default PATH, so it was not pursued.
- Musl-based images (Alpine) need the `linux-*-musl` build. Harbor installs through npm there, and the cache does not cover it yet.
- The manifest is fetched over HTTPS but its GPG signature is not checked yet. That is on the roadmap.

## Alternatives considered

- **Raise Harbor's setup timeout.** It would work eventually, at the cost of about 7 minutes and 480 MB of downloads per trial. It fixes nothing about reproducibility.
- **Bake the harness into task images.** Fast, but it couples tasks to harness versions. The harness version is a pin dimension, not a task property.
- **A local HTTP mirror of downloads.claude.ai.** General, but it adds a service to run. A mount is simpler for a single-host v0.1.
