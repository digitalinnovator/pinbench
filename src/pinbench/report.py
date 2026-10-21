"""Static HTML report with per-task trace drill-down. A derived artefact outside the bundle."""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from pinbench.bundle import RunBundle
from pinbench.models import TrialRecord, Verdict

_MAX_STEPS = 80
_MAX_TEXT = 700


def _clip(text: str, limit: int = _MAX_TEXT) -> str:
    return text if len(text) <= limit else text[:limit] + f" … [{len(text) - limit} more chars]"


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for part in value:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
            elif isinstance(part, dict):
                parts.append(f"[{part.get('type', 'part')}]")
            else:
                parts.append(str(part))
        return "\n".join(parts)
    return json.dumps(value, ensure_ascii=False)


def load_transcript(trial_path: Path) -> list[dict[str, Any]] | None:
    """Condensed steps from an ATIF trajectory (agent/trajectory.json), if the harness wrote one."""
    path = trial_path / "agent" / "trajectory.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    steps = []
    for step in data.get("steps", [])[:_MAX_STEPS]:
        calls = [
            {
                "name": c.get("function_name", "?"),
                "args": _clip(json.dumps(c.get("arguments", {}), ensure_ascii=False), 400),
            }
            for c in step.get("tool_calls") or []
        ]
        results = [
            _clip(_as_text(r.get("content")), 400)
            for r in (step.get("observation") or {}).get("results", [])
        ]
        steps.append(
            {
                "id": step.get("step_id"),
                "source": step.get("source", "?"),
                "message": _clip(_as_text(step.get("message"))),
                "calls": calls,
                "results": results,
            }
        )
    return steps


def _e_chart(verdict: Verdict, width: int = 560, height: int = 180) -> dict[str, Any] | None:
    """Coordinates for an inline SVG of log10(E) per batch against the 1/alpha threshold."""
    if not verdict.history:
        return None
    ys = [math.log10(max(p.e_value, 1e-12)) for p in verdict.history]
    threshold = math.log10(1.0 / verdict.alpha)
    lo, hi = min([*ys, -1.0]), max([*ys, threshold + 0.5])
    pad = 28
    n = len(ys)

    def x(i: int) -> float:
        return pad + (width - 2 * pad) * (i / max(n - 1, 1))

    def y(v: float) -> float:
        return height - pad - (height - 2 * pad) * ((v - lo) / (hi - lo))

    return {
        "width": width,
        "height": height,
        "points": " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(ys)),
        "dots": [(x(i), y(v), verdict.history[i].batch) for i, v in enumerate(ys)],
        "threshold_y": y(threshold),
        "zero_y": y(0.0),
        "threshold_label": f"1/\u03b1 = {1.0 / verdict.alpha:g}",
        "pad": pad,
    }


def render_report(bundle: RunBundle, out_path: Path) -> Path:
    manifest = bundle.manifest()
    verdict = bundle.verdict()
    trials = bundle.trials()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def link(rel: str | None, *parts: str) -> str | None:
        if rel is None:
            return None
        target = bundle.path.joinpath(rel, *parts)
        return os.path.relpath(target, out_path.parent) if target.exists() else None

    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in sorted(trials, key=lambda r: (r.task, r.batch, r.pin, r.trial_name)):
        by_task[t.task].append(_trial_view(t, bundle, link))

    env = Environment(
        loader=PackageLoader("pinbench", "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    html = env.get_template("report.html.j2").render(
        manifest=manifest,
        verdict=verdict,
        chart=_e_chart(verdict) if verdict else None,
        pins={p.name: p for p in manifest.pins},
        by_task=dict(by_task),
        n_trials=len(trials),
    )
    out_path.write_text(html)
    return out_path


def _trial_view(t: TrialRecord, bundle: RunBundle, link: Any) -> dict[str, Any]:
    transcript = load_transcript(bundle.path / t.trial_dir) if t.trial_dir else None
    return {
        "r": t,
        "result_link": link(t.trial_dir, "result.json"),
        "agent_link": link(t.trial_dir, "agent"),
        "verifier_link": link(t.trial_dir, "verifier"),
        "transcript": transcript,
    }
