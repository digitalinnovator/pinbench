# Power simulation: pass-rate regression detection

**Simulated, not measured.** Seed 20260927; 2000 simulated compare runs per row; alpha = 0.05; budget = 20 batches; baseline pass rate centred on 60% with task spread sigma = 1.5 on the logit scale; one attempt per task per arm per batch. Dollars assume $0.50 per trial, a placeholder until measured harness costs replace it.

Each e-process cell: detection rate within budget / median batches to detection / mean spend including runs that never detect. Rows with `drop = 0` are false-alarm rates and should be at or below alpha.

| Tasks | Drop | e-process q≤1 | e-process q≤0.8 | e-process q≤0.7 | Fixed-N McNemar | McNemar re-checked each batch | Discordance |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 0% | 1.7% / 7 / $198 | 1.7% / 11 / $198 | 1.1% / 16 / $199 | 3.5% | 14.2% | 0.35 |
| 10 | 5% | 10.4% / 10 / $190 | 12.3% / 11 / $189 | 10.9% / 14 / $193 | 29.6% | 46.9% | 0.35 |
| 10 | 10% | 43.3% / 11 / $160 | 46.9% / 11 / $159 | 46.7% / 13 / $167 | 72.9% | 83.3% | 0.36 |
| 10 | 20% | 97.7% / 6 / $75 | 98.7% / 7 / $76 | 98.8% / 8 / $90 | 99.8% | 99.9% | 0.39 |
| 25 | 0% | 2.1% / 3 / $492 | 2.1% / 5 / $494 | 2.5% / 8 / $494 | 4.8% | 17.1% | 0.35 |
| 25 | 5% | 22.5% / 10 / $445 | 27.4% / 11 / $436 | 30.9% / 11 / $435 | 58.0% | 73.7% | 0.35 |
| 25 | 10% | 81.2% / 9 / $286 | 86.1% / 8 / $266 | 88.3% / 8 / $266 | 97.4% | 98.4% | 0.36 |
| 25 | 20% | 100.0% / 3 / $89 | 100.0% / 3 / $88 | 100.0% / 4 / $101 | 100.0% | 100.0% | 0.39 |
| 50 | 0% | 1.0% / 4 / $993 | 1.4% / 4 / $991 | 1.4% / 5 / $991 | 4.9% | 18.8% | 0.35 |
| 50 | 5% | 42.9% / 12 / $812 | 49.2% / 11 / $770 | 54.6% / 10 / $743 | 83.7% | 90.3% | 0.35 |
| 50 | 10% | 98.9% / 6 / $346 | 99.3% / 5 / $312 | 99.5% / 5 / $303 | 100.0% | 100.0% | 0.36 |
| 50 | 20% | 100.0% / 2 / $105 | 100.0% / 2 / $101 | 100.0% / 2 / $115 | 100.0% | 100.0% | 0.39 |

How to read it:

- **False alarms (drop = 0).** Re-checking a fixed-sample test after every batch is what a naive canary does. Compare its false-alarm rate with the e-process columns.
- **Power.** The fixed-N test gets one look at the full budget and always pays for all of it. The e-process pays only until it is sure.
- **Mixture bound.** A lower q_max concentrates evidence on small regressions, the ones that matter for a canary. Every bound keeps the false-alarm guarantee (ADR-0003).
- **Discordance** is the share of task-batches where the two arms disagree. Only those carry evidence, so tasks that always pass or always fail cost money for nothing.

Regenerate with `uv run python benchmarks/power_simulation.py`.
