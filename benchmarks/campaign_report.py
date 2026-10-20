"""The October 2026 benchmark campaign: export its evidence, then rebuild every published number.

Run bundles live under each suite's `.canary/runs/` and are not committed (they hold full
transcripts, tens of megabytes). This script copies the part every published number depends on,
each bundle's `manifest.json`, `trials.jsonl`, `verdict.json` and `SHA256SUMS`, into
`benchmarks/results/campaign-2026-10/`, and checks each copied file against its bundle's checksum.
The report is then built from those committed files alone, so anyone can rebuild it:

    uv run python benchmarks/campaign_report.py export    # from local bundles (owner's machine)
    uv run python benchmarks/campaign_report.py report    # from the committed files; writes the .md

Every number in the README's benchmark section comes from the report this writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scipy.stats import binom

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "benchmarks" / "results" / "campaign-2026-10"
REPORT = REPO / "benchmarks" / "results" / "campaign-2026-10.md"
FILES = ("manifest.json", "trials.jsonl", "verdict.json", "SHA256SUMS")


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    suite: str  # directory holding the suite's canary.toml, relative to the repo
    run_id: str


STEPS = [
    Step("1-h45", "Smoke: Haiku 4.5 baseline", "examples/smoke", "20261019T101312Z-run-02dbad"),
    Step(
        "1-h45-terse",
        "Smoke: appended system prompt",
        "examples/smoke",
        "20261019T101509Z-run-86d625",
    ),
    Step(
        "1-h45-no-cache",
        "Smoke: prompt caching off",
        "examples/smoke",
        "20261019T101620Z-run-c1012e",
    ),
    Step("1-h45-turn-cap", "Smoke: turn cap", "examples/smoke", "20261019T101730Z-run-48b01a"),
    Step("1-h45-spend-cap", "Smoke: spend cap", "examples/smoke", "20261019T101908Z-run-89299f"),
    Step(
        "1-s5-high", "Smoke: Sonnet 5, effort high", "examples/smoke", "20261019T102031Z-run-1018c1"
    ),
    Step(
        "1-s5-low", "Smoke: Sonnet 5, effort low", "examples/smoke", "20261019T102146Z-run-208d83"
    ),
    Step(
        "2-release",
        "Release check: 2.1.283 against 2.1.303",
        "examples/demo-suite",
        "20261019T110142Z-compare-99a38e",
    ),
    Step("3-v2.1.66", "Old build 2.1.66", "examples/smoke", "20261019T111053Z-run-d63e03"),
    Step("3-v2.1.85", "Old build 2.1.85", "examples/smoke", "20261019T111911Z-run-06df76"),
    Step("3-v2.1.112", "Old build 2.1.112", "examples/smoke", "20261019T112356Z-run-8f8864"),
    Step(
        "4-calibration",
        "Price check: Sonnet 5 high on 18 tasks",
        "examples/benchmark-suite",
        "20261020T172942Z-run-312890",
    ),
    Step(
        "5-headline",
        "Headline: effort high against low, batches 0-4",
        "examples/benchmark-suite",
        "20261020T174900Z-compare-98c8b5",
    ),
    Step(
        "7-extension",
        "Headline: pre-registered extra batch 5",
        "examples/benchmark-suite",
        "20261020T195046Z-compare-3053f5",
    ),
    Step(
        "6-cache",
        "Caching off: cost check",
        "examples/benchmark-suite",
        "20261020T202808Z-compare-46fc4b",
    ),
    Step(
        "X1-codex-high",
        "Codex spike: effort high",
        "examples/codex-spike",
        "20261020T172942Z-run-3c9b77",
    ),
    Step(
        "X1-codex-low",
        "Codex spike: effort low",
        "examples/codex-spike",
        "20261020T173356Z-run-8f24e9",
    ),
    Step(
        "C0-codex-calibration",
        "Codex price check: high on 18 tasks",
        "examples/benchmark-suite-codex",
        "20261020T194637Z-run-f2d77a",
    ),
    Step(
        "C1-codex-headroom",
        "Codex headroom: high against low on 32 tasks, 2 attempts",
        "examples/benchmark-suite-codex",
        "20261020T202808Z-compare-b725f2",
    ),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export() -> None:
    for step in STEPS:
        bundle = REPO / step.suite / ".canary" / "runs" / step.run_id
        if not bundle.is_dir():
            sys.exit(f"{step.key}: bundle {bundle} not found")
        sums = dict(
            reversed(line.split("  ", 1))  # type: ignore[misc]
            for line in (bundle / "SHA256SUMS").read_text().splitlines()
            if line
        )
        dest = EVIDENCE / step.run_id
        dest.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            src = bundle / name
            if not src.exists():
                continue
            if name != "SHA256SUMS" and sums.get(name) != _sha256(src):
                sys.exit(f"{step.key}: {name} does not match its bundle checksum")
            target = dest / name
            if target.exists():
                target.chmod(0o644)
            shutil.copyfile(src, target)
            target.chmod(0o644)
    print(f"exported {len(STEPS)} runs to {EVIDENCE.relative_to(REPO)}")


# -- reading the committed evidence --------------------------------------------------------------


def _load(step: Step) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    d = EVIDENCE / step.run_id
    manifest = json.loads((d / "manifest.json").read_text())
    trials = [json.loads(line) for line in (d / "trials.jsonl").read_text().splitlines() if line]
    verdict_path = d / "verdict.json"
    verdict = json.loads(verdict_path.read_text()) if verdict_path.exists() else None
    sums = dict(
        reversed(line.split("  ", 1))  # type: ignore[misc]
        for line in (d / "SHA256SUMS").read_text().splitlines()
        if line
    )
    for name in ("manifest.json", "trials.jsonl", "verdict.json"):
        if (d / name).exists() and sums.get(name) != _sha256(d / name):
            sys.exit(f"{step.key}: committed {name} does not match the bundle's SHA256SUMS")
    return manifest, trials, verdict


def _cost(trial: dict[str, Any]) -> float:
    return float(trial.get("cost_usd") or trial.get("reported_cost_usd") or 0.0)


def _money(x: float) -> str:
    return f"${x:,.2f}" if x >= 0.1 else f"${x:.3f}"


def report() -> str:
    data = {s.key: (s, *_load(s)) for s in STEPS}
    out: list[str] = []
    w = out.append

    w("# Benchmark campaign, October 2026\n")
    w(
        "Generated by `benchmarks/campaign_report.py report` from the committed evidence in "
        "`benchmarks/results/campaign-2026-10/` (each run's manifest, trials and verdict, checked "
        "against its bundle's checksums). Do not edit by hand.\n"
    )

    # -- spend ------------------------------------------------------------------------------
    w("## What each step cost\n")
    w("| Step | Run | Trials | Cost |")
    w("|---|---|---|---|")
    pools: dict[str, float] = {}
    for step, manifest, trials, _verdict in data.values():
        cost = sum(_cost(t) for t in trials)
        pool = (
            "openai"
            if any("openai/" in str(p["spec"].get("model")) for p in manifest["pins"])
            else "anthropic"
        )
        pools[pool] = pools.get(pool, 0.0) + cost
        w(f"| {step.title} | `{step.run_id}` | {len(trials)} | {_money(cost)} |")
    w("")
    w(
        "**Total measured cost:** "
        + ", ".join(f"{pool} {_money(c)}" for pool, c in sorted(pools.items()))
        + ". The first, failed smoke attempt (revoked key) cost nothing and is not listed.\n"
    )

    # -- headline -----------------------------------------------------------------------------
    _s, manifest5, trials5, v5 = data["5-headline"]
    _s, _m7, trials7, v7 = data["7-extension"]
    assert v5 is not None
    assert v7 is not None
    w("## Headline: Claude Code, reasoning effort high against low\n")
    pins = {p["name"]: p["spec"] for p in manifest5["pins"]}
    hi, lo = pins[manifest5["baseline"]], pins[manifest5["candidate"]]
    w(
        f"Claude Code {hi['version']} on `{hi['model']}`; `{manifest5['baseline']}` "
        f"(effort {hi['options']['reasoning_effort']}) against `{manifest5['candidate']}` "
        f"(effort {lo['options']['reasoning_effort']}); {len(manifest5['tasks'])} tasks, one "
        "attempt per task per arm per batch; the canary's paired mixture e-process at "
        f"α = {v5['alpha']} (threshold {1 / v5['alpha']:g}).\n"
    )
    w("| Batch | Pairs | Discordant | Regressed | Improved | E | Cumulative cost |")
    w("|---|---|---|---|---|---|---|")
    for p in v7["history"]:
        w(
            f"| {p['batch']} | {p['n_pairs']} | {p['n_discordant']} | {p['n_regress']} | "
            f"{p['n_improve']} | {p['e_value']:.2f} | {_money(p['spent_usd'])} |"
        )
    w("")
    all_trials = trials5 + trials7
    for verdict, label in ((v5, "pre-registered cap, 5 batches"), (v7, "with the extra batch, 6")):
        b, c = verdict["baseline"], verdict["candidate"]
        w(
            f"- **{label}:** {verdict['decision']}, E = {verdict['e_value']:.2f}, anytime-valid "
            f"p ≤ {verdict['p_value']:.3f}; pass rate {b['passes']}/{b['n']} "
            f"({100 * b['passes'] / b['n']:.0f}%) against {c['passes']}/{c['n']} "
            f"({100 * c['passes'] / c['n']:.0f}%); {verdict['n_regress']} regressed and "
            f"{verdict['n_improve']} improved pairs."
        )
    k, n = v5["n_regress"], v5["n_regress"] + v5["n_improve"]
    p_one = float(binom.sf(k - 1, n, 0.5))
    w(
        f"- **Fixed-sample comparison at the pre-registered cap:** exact McNemar test on the "
        f"{n} discordant pairs of batches 0–4, one-sided p = {p_one:.3f} (two-sided "
        f"{min(1.0, 2 * p_one):.3f}). Valid only at the cap fixed in advance; the extra batch was "
        "decided after looking, which the e-process allows and a fixed-sample test does not."
    )
    w("")
    w(
        "Cost, tokens and latency, low effort relative to high "
        "(cluster bootstrap over tasks, warm-up batch excluded):\n"
    )
    w("| Metric | Ratio | 95% interval |")
    w("|---|---|---|")
    for m in v7["metrics"]:
        w(f"| {m['metric']} | ×{m['ratio']:.2f} | {m['ci_low']:.2f}–{m['ci_high']:.2f} |")
    w("")
    by_pin: dict[str, list[dict[str, Any]]] = {}
    for t in all_trials:
        by_pin.setdefault(t["pin"], []).append(t)
    for pin, ts in by_pin.items():
        claims = [
            t for t in ts if (t.get("claim_check") or {}).get("verdict") not in (None, "no_claim")
        ]
        false = [t for t in claims if t["claim_check"]["verdict"] == "false_success"]
        claimed_failed = [t for t in claims if t["status"] == "fail"]
        w(
            f"- `{pin}`: mean cost {_money(statistics.mean(_cost(t) for t in ts))} per trial; "
            f'"tests pass" claimed in {len(claims)} of {len(ts)} trials, '
            f"{len(false)} contradicted by the transcript, {len(claimed_failed)} followed by "
            "failing hidden tests."
        )
    w("")

    # -- caching ------------------------------------------------------------------------------
    _s, manifest6, _t6, v6 = data["6-cache"]
    assert v6 is not None
    w("## Caching off: the cost regression\n")
    w(
        f"`{manifest6['baseline']}` against `{manifest6['candidate']}` "
        f"(`DISABLE_PROMPT_CACHING=1`), {len(manifest6['tasks'])} tasks, one batch.\n"
    )
    w("| Metric | Ratio | 95% interval | Flagged |")
    w("|---|---|---|---|")
    for m in v6["metrics"]:
        w(
            f"| {m['metric']} | ×{m['ratio']:.2f} | {m['ci_low']:.2f}–{m['ci_high']:.2f} | "
            f"{'yes' if m['flagged'] else ''} |"
        )
    w("")

    # -- harness checks -----------------------------------------------------------------------
    w("## Harness checks\n")
    w("| Run | Pin | Status | Version proven | Harness stop | Cost |")
    w("|---|---|---|---|---|---|")
    for key in (
        "1-h45",
        "1-h45-terse",
        "1-h45-no-cache",
        "1-h45-turn-cap",
        "1-h45-spend-cap",
        "1-s5-high",
        "1-s5-low",
        "3-v2.1.66",
        "3-v2.1.85",
        "3-v2.1.112",
        "X1-codex-high",
        "X1-codex-low",
    ):
        step, _m, ts, _v = data[key]
        for t in ts:
            proof = f"{t['installed_version']} ({t['version_source']})"
            w(
                f"| {step.title} | `{t['pin']}` | {t['status']} | {proof} | "
                f"{t.get('harness_stop') or '—'} | {_money(_cost(t))} |"
            )
    w("")
    _s, _m2, _t2, v2 = data["2-release"]
    assert v2 is not None
    w(
        f"Release check: {v2['baseline']['passes']}/{v2['baseline']['n']} against "
        f"{v2['candidate']['passes']}/{v2['candidate']['n']}, {v2['decision']}; "
        + "; ".join(
            f"{m['metric']} ×{m['ratio']:.2f} ({m['ci_low']:.2f}–{m['ci_high']:.2f})"
            for m in v2["metrics"]
        )
        + ".\n"
    )
    for key in ("4-calibration", "C0-codex-calibration"):
        step, _m, ts, _v = data[key]
        costs = [_cost(t) for t in ts]
        w(
            f"{step.title}: {sum(t['status'] == 'pass' for t in ts)}/{len(ts)} passed; cost per "
            f"trial mean {_money(statistics.mean(costs))}, highest {_money(max(costs))}.\n"
        )
    # -- codex and the efficiency index ---------------------------------------------------------
    _s, manifest_c1, _tc1, vc1 = data["C1-codex-headroom"]
    assert vc1 is not None
    w("## Codex: effort high against low (headroom check)\n")
    b, c = vc1["baseline"], vc1["candidate"]
    w(
        f"Codex on `gpt-6-luna`, {len(manifest_c1['tasks'])} tasks, 2 attempts each: "
        f"{b['passes']}/{b['n']} at high effort against {c['passes']}/{c['n']} at low; "
        f"{vc1['n_regress']} regressed and {vc1['n_improve']} improved pairs, "
        f"E = {vc1['e_value']:.2f}. The suite has no headroom for this stack.\n"
    )
    w("| Metric | Low / high | 95% interval |")
    w("|---|---|---|")
    for m in vc1["metrics"]:
        w(f"| {m['metric']} | ×{m['ratio']:.2f} | {m['ci_low']:.2f}–{m['ci_high']:.2f} |")
    w("")
    w("## Efficiency index: dollars per solved task\n")
    w(
        "The same 18 tasks, one attempt each at high effort. This compares harness-and-model "
        "stacks at their list prices, not harnesses alone. It is also biased against the first "
        "row: these tasks were chosen because Sonnet 5 sometimes fails them.\n"
    )
    w("| Stack | Passed | Cost per trial | Cost per solved task |")
    w("|---|---|---|---|")
    for key in ("4-calibration", "C0-codex-calibration"):
        _st, manifest_k, ts, _v = data[key]
        spec = manifest_k["pins"][0]["spec"]
        solved = sum(t["status"] == "pass" for t in ts)
        total = sum(_cost(t) for t in ts)
        w(
            f"| {spec['harness']} {spec['version']}, `{spec['model']}` | {solved}/{len(ts)} | "
            f"{_money(total / len(ts))} | {_money(total / solved) if solved else '—'} |"
        )
    w("")
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["export", "report"])
    args = parser.parse_args()
    if args.action == "export":
        export()
    else:
        REPORT.write_text(report())
        print(f"wrote {REPORT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
