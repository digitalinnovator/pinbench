"""The October 2026 benchmark campaign: export its evidence, then rebuild every published number.

Run bundles live under each suite's `.pinbench/runs/` and are not committed (they hold full
transcripts, tens of megabytes). This script copies the part every published number depends on,
each bundle's `manifest.json`, `trials.jsonl`, `verdict.json` and `SHA256SUMS`, into
`benchmarks/results/campaign-2026-10/`, and checks each copied file against its bundle's checksum.
It also re-checks every transcript's "tests pass" claim with the current verifier rules and writes
the verdicts next to them (`claims.jsonl`), because a bundle keeps the verdicts of the rules it ran
with.
The report is then built from those committed files alone, so anyone can rebuild it:

    uv run python benchmarks/campaign_report.py export    # from the local run bundles
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

from scipy.stats import beta, binom

from pinbench.verifier import RULES_VERSION, check_trial

REPO = Path(__file__).resolve().parent.parent
EVIDENCE = REPO / "benchmarks" / "results" / "campaign-2026-10"
REPORT = REPO / "benchmarks" / "results" / "campaign-2026-10.md"
FILES = ("manifest.json", "trials.jsonl", "verdict.json", "SHA256SUMS")


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    suite: str  # directory holding the suite's pinbench.toml, relative to the repo
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
        "Headline: extra batch 5 (planned; run before step 6)",
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
    Step(
        "C2-codex-none-probe",
        "Codex probe: effort none on 18 tasks",
        "examples/benchmark-suite-codex",
        "20261021T020615Z-run-02a846",
    ),
    Step(
        "V1-verbosity",
        "Verbosity check: appended instruction on Haiku 4.5",
        "examples/demo-suite",
        "20261021T125246Z-compare-64e6e7",
    ),
    *(
        Step(f"R-{label}", title, "examples/benchmark-suite-codex", run_id)
        for label, title, run_id in (
            ("det1", "Codex replicated: detection run 1", "20261021T030101Z-compare-b295f8"),
            ("det2", "Codex replicated: detection run 2", "20261021T034602Z-compare-c037da"),
            ("det3", "Codex replicated: detection run 3", "20261021T041401Z-compare-b4d862"),
            ("det4", "Codex replicated: detection run 4", "20261021T030122Z-compare-aae17d"),
            ("det5", "Codex replicated: detection run 5", "20261021T034624Z-compare-54eac1"),
            ("aa1", "Codex replicated: identical arms, run 1", "20261021T042719Z-compare-32ee06"),
            ("aa2", "Codex replicated: identical arms, run 2", "20261021T041457Z-compare-1f52c5"),
        )
    ),
]
DETECTION = ("R-det1", "R-det2", "R-det3", "R-det4", "R-det5")
IDENTICAL = ("R-aa1", "R-aa2")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export() -> None:
    for step in STEPS:
        bundle = REPO / step.suite / ".pinbench" / "runs" / step.run_id
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
        rows = []
        for line in (bundle / "trials.jsonl").read_text().splitlines():
            trial = json.loads(line) if line else None
            if not trial or not trial.get("trial_dir") or trial["status"] == "error":
                continue
            check = check_trial(bundle / trial["trial_dir"])
            if check is not None:
                rows.append({"trial_name": trial["trial_name"], **check.model_dump(mode="json")})
        (dest / "claims.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    where = EVIDENCE.relative_to(REPO)
    print(f"exported {len(STEPS)} runs to {where} (claims: rules v{RULES_VERSION})")


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


def _claims(step: Step) -> dict[str, dict[str, Any]]:
    """Claim verdicts by trial name, from the export's re-check with the current rules."""
    path = EVIDENCE / step.run_id / "claims.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    return {r["trial_name"]: r for r in rows}


def _claim_line(pin: str, trials: list[dict[str, Any]], claims: dict[str, Any]) -> str:
    checked = [(t, claims[t["trial_name"]]) for t in trials if t["trial_name"] in claims]
    claimed = [(t, c) for t, c in checked if c["verdict"] != "no_claim"]
    n = {v: sum(c["verdict"] == v for _, c in claimed) for v in ("supported", "false_success")}
    failed = sum(t["status"] == "fail" for t, _ in claimed)
    return (
        f'`{pin}`: "tests pass" claimed in {len(claimed)} of {len(checked)} trials; '
        f"{n['supported']} backed by a passing test run after the last edit, "
        f"{n['false_success']} not, {len(claimed) - sum(n.values())} unverifiable; "
        f"the hidden tests then failed in {failed} of them."
    )


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
        "attempt per task per arm per batch; pinbench's paired mixture e-process at "
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
    claims5 = {**_claims(data["5-headline"][0]), **_claims(data["7-extension"][0])}
    w(f"Claim checks (verifier rules v{RULES_VERSION}):\n")
    for pin, ts in by_pin.items():
        w(
            f"- Mean cost {_money(statistics.mean(_cost(t) for t in ts))} per trial; "
            + _claim_line(pin, ts, claims5)
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

    if "V1-verbosity" in data:
        w(_verbosity(data))
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
    w(_repricing(data))
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
    _s, _mp, trials_probe, _vp = data["C2-codex-none-probe"]
    w(
        f"A one-trial probe at effort `none` on the 18 tasks of the efficiency index passed "
        f"{sum(t['status'] == 'pass' for t in trials_probe)}/{len(trials_probe)}, for "
        f"{_money(sum(_cost(t) for t in trials_probe))}. That gap led to the replicated "
        "benchmark below.\n"
    )
    w(_replicated(data))
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


def _replicated(data: dict[str, Any]) -> str:
    """The pre-registered replicated Codex benchmark (docs/benchmark/plan.md)."""
    out: list[str] = []
    w = out.append
    _s, manifest, _t, _v = data[DETECTION[0]]
    pins = {p["name"]: p["spec"] for p in manifest["pins"]}
    hi, lo = pins[manifest["baseline"]], pins[manifest["candidate"]]
    w("## Codex: replicated detection benchmark\n")
    w(
        f"Codex {hi['version']} on `{hi['model']}`, {len(manifest['tasks'])} tasks, effort "
        f"`{hi['options']['reasoning_effort']}` against `{lo['options']['reasoning_effort']}`, "
        "five independent runs; and two runs of identical arms, which should never be flagged. "
        "Each run: one attempt per task per arm per batch, at most 6 batches, futility look "
        "after batch 3. The protocol was committed before the first run.\n"
    )
    w(
        "| Run | Decision | Stopped by | Batches | Pairs | Regressed / improved | E | Passed "
        "| Cost |"
    )
    w("|---|---|---|---|---|---|---|---|---|")
    for key in DETECTION + IDENTICAL:
        step, _m, _ts, v = data[key]
        assert v is not None
        b, c = v["baseline"], v["candidate"]
        w(
            f"| {step.title.split(': ', 1)[1]} | {v['decision']} | {v['stop_reason']} | "
            f"{len(v['history'])} | {v['n_pairs']} | {v['n_regress']} / {v['n_improve']} | "
            f"{v['e_value']:.1f} | {b['passes']}/{b['n']} against {c['passes']}/{c['n']} | "
            f"{_money(v['history'][-1]['spent_usd'])} |"
        )
    w("")
    for label, keys in (("Detection runs", DETECTION), ("Identical-arm runs", IDENTICAL)):
        vs = [data[k][3] for k in keys]
        ts = [t for k in keys for t in data[k][2]]
        bp, bn = sum(v["baseline"]["passes"] for v in vs), sum(v["baseline"]["n"] for v in vs)
        cp, cn = sum(v["candidate"]["passes"] for v in vs), sum(v["candidate"]["n"] for v in vs)
        total = sum(_cost(t) for t in ts)
        w(
            f"- **{label}, pooled:** {bp}/{bn} ({100 * bp / bn:.0f}%) against {cp}/{cn} "
            f"({100 * cp / cn:.0f}%); {len(ts)} trials, {_money(total)} "
            f"({_money(total / len(ts))} per trial)."
        )
    det = [data[k][3] for k in DETECTION]
    flagged = [v for v in det if v["decision"] == "regression"]
    k, n = len(flagged), len(det)
    low = float(beta.ppf(0.025, k, n - k + 1)) if k else 0.0
    high = float(beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
    w(
        f"- **Detected in {k} of {n} runs** (95% Clopper–Pearson interval for the detection "
        f"rate at this effect size: {100 * low:.0f}%–{100 * high:.0f}%)."
    )
    if flagged:
        trials = [2 * v["n_pairs"] for v in flagged]
        dollars = [v["history"][-1]["spent_usd"] for v in flagged]
        w(
            f"- **To flag:** median {statistics.median(trials):g} trials "
            f"(range {min(trials)}–{max(trials)}) and median {_money(statistics.median(dollars))} "
            f"(range {_money(min(dollars))}–{_money(max(dollars))}), both arms counted."
        )
    aa = [data[k][3] for k in IDENTICAL]
    false_alarms = sum(v["decision"] != "inconclusive" for v in aa)
    w(
        f"- **Identical arms:** {false_alarms} of {len(aa)} runs flagged anything; "
        + "; ".join(
            f"cost ×{m['ratio']:.2f} ({m['ci_low']:.2f}–{m['ci_high']:.2f})"
            for v in aa
            for m in v["metrics"]
            if m["metric"] == "cost_usd"
        )
        + ". Two runs say little about the false-alarm rate; that rests on the test's "
        "guarantee (at most 5%)."
    )
    ratios = [m for v in det for m in v["metrics"] if m["metric"] == "cost_usd"]
    w(
        f"- **Cost at effort none relative to high:** ×{min(m['ratio'] for m in ratios):.2f} to "
        f"×{max(m['ratio'] for m in ratios):.2f} across the five detection runs."
    )
    by_pin: dict[str, list[dict[str, Any]]] = {}
    claims: dict[str, Any] = {}
    for key in DETECTION + IDENTICAL:
        step, _m, ts, _v = data[key]
        claims.update(_claims(step))
        for t in ts:
            by_pin.setdefault(t["pin"], []).append(t)
    w(f"- **Claim checks** across the seven runs (verifier rules v{RULES_VERSION}):")
    for pin, ts in by_pin.items():
        w(f"  - {_claim_line(pin, ts, claims)}")
    errors = sum(v["baseline"]["errors"] + v["candidate"]["errors"] for v in det + aa)
    w(
        f"- **Infrastructure errors:** {errors} {'trial' if errors == 1 else 'trials'} across the "
        "seven runs, left out of the pairs as pinbench always does."
    )
    w(
        "- **Caveats:** effort `none` is a much larger cut than the postmortem's change, on a "
        "different model; five runs give only a rough detection rate."
    )
    w("")
    return "\n".join(out)


def _verbosity(data: dict[str, Any]) -> str:
    """The verbosity check: the postmortem's third change (docs/benchmark/plan.md)."""
    out: list[str] = []
    w = out.append
    _s, manifest, trials, v = data["V1-verbosity"]
    assert v is not None
    pins = {p["name"]: p["spec"] for p in manifest["pins"]}
    base = pins[manifest["baseline"]]
    w("## Verbosity instruction: the third postmortem change\n")
    w(
        f"Claude Code {base['version']} on `{base['model']}`, `{manifest['baseline']}` against "
        f"`{manifest['candidate']}` (an appended instruction to keep every response under 25 "
        f"words), {len(manifest['tasks'])} tasks, one attempt per task per arm per batch.\n"
    )
    b, c = v["baseline"], v["candidate"]
    w(
        f"- **{v['decision']}** after {len(v['history'])} batches (stopped by {v['stop_reason']}): "
        f"pass rate {b['passes']}/{b['n']} against {c['passes']}/{c['n']}; {v['n_regress']} "
        f"regressed and {v['n_improve']} improved pairs; E = {v['e_value']:.2f}; "
        f"{len(trials)} trials, {_money(sum(_cost(t) for t in trials))}."
    )
    w(
        "- Terse relative to baseline (cluster bootstrap over only "
        f"{len(manifest['tasks'])} tasks, so the intervals are far too narrow; warm-up batch "
        "excluded):\n"
    )
    w("| Metric | Ratio | 95% interval |")
    w("|---|---|---|")
    for m in v["metrics"]:
        w(f"| {m['metric']} | ×{m['ratio']:.2f} | {m['ci_low']:.2f}–{m['ci_high']:.2f} |")
    w("")
    return "\n".join(out)


def _repricing(data: dict[str, Any]) -> str:
    """How often the re-priced cost (ADR-0005) equals the cost the harness reported."""
    both = [
        t
        for _s, _m, ts, _v in data.values()
        for t in ts
        if t.get("cost_usd") is not None and t.get("reported_cost_usd") is not None
    ]
    off = [t for t in both if abs(t["cost_usd"] - t["reported_cost_usd"]) > 0.0005]
    lines = [
        f"Re-priced cost against harness-reported cost: {len(both) - len(off)} of {len(both)} "
        "trials with both figures agree within $0.0005."
    ]
    for t in off:
        diff = t["cost_usd"] / t["reported_cost_usd"] - 1
        lines.append(
            f"- `{t['trial_name']}` (`{t['pin']}`): re-priced {_money(t['cost_usd'])}, reported "
            f"{_money(t['reported_cost_usd'])} ({100 * diff:+.0f}%)."
        )
    return "\n".join(lines) + "\n"


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
