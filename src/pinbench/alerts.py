"""Alerts for a finished compare run: a Slack incoming webhook and a GitHub issue.

Alerts are a side effect after the bundle is sealed. A failed delivery is logged and reported, and
never changes the verdict or the exit code. Credentials come from the process environment, named
in `[alerts]`; they are never read from pinbench.toml and never written to logs or bundles.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from pinbench.config import AlertsConfig
from pinbench.http import Http, HttpError, https_request
from pinbench.models import ArmSummary, RunManifest, Verdict

log = logging.getLogger(__name__)

_USER_AGENT = "pinbench"
# Token counts are reported, but only dollars and seconds raise a cost alert.
_COST_METRICS = frozenset({"cost_usd", "reported_cost_usd", "agent_seconds"})


class AlertError(RuntimeError):
    pass


@dataclass(frozen=True)
class Alert:
    title: str  # stable per (suite, baseline, candidate): the GitHub de-duplication key
    reasons: tuple[str, ...]
    markdown: str
    slack_text: str


@dataclass(frozen=True)
class Delivery:
    channel: str
    ok: bool
    detail: str


def alert_reasons(verdict: Verdict, on: list[str]) -> tuple[str, ...]:
    """Which configured conditions this verdict meets, in a fixed order."""
    found = []
    if "regression" in on and verdict.decision == "regression":
        found.append("regression")
    if "cost_increase" in on and any(
        m.flagged and m.metric in _COST_METRICS for m in verdict.metrics
    ):
        found.append("cost_increase")
    if "false_success" in on and verdict.candidate.false_success > verdict.baseline.false_success:
        found.append("false_success")
    return tuple(found)


def _rate(arm: ArmSummary) -> str:
    return f"{arm.passes}/{arm.n}" + (f" ({100 * arm.passes / arm.n:.0f}%)" if arm.n else "")


def _pin_line(manifest: RunManifest, name: str) -> str:
    spec = next(p.spec for p in manifest.pins if p.name == name)
    return f"{spec.get('harness')}@{spec.get('version') or '-'}, model {spec.get('model') or '-'}"


def _pin_diff(manifest: RunManifest, baseline: str, candidate: str) -> str:
    """The spec fields in which the two pins differ, e.g. `version: 2.1.283 -> 2.1.285`."""
    specs = {p.name: p.spec for p in manifest.pins}
    a, b = specs[baseline], specs[candidate]
    parts = []
    for key in sorted(set(a) | set(b)):
        x, y = a.get(key), b.get(key)
        if x == y:
            continue
        if isinstance(x, dict) and isinstance(y, dict):
            parts += [
                f"{key}.{k}: {x.get(k)!r} -> {y.get(k)!r}"
                for k in sorted(set(x) | set(y))
                if x.get(k) != y.get(k)
            ]
        else:
            parts.append(f"{key}: {x!r} -> {y!r}")
    return "; ".join(parts) or "nothing (identical specs)"


def build_alert(manifest: RunManifest, verdict: Verdict, reasons: tuple[str, ...]) -> Alert:
    base, cand = verdict.baseline, verdict.candidate
    headline = {
        "regression": "pass-rate regression",
        "cost_increase": "cost or latency increase",
        "false_success": "more false-success claims",
    }
    what = ", ".join(headline[r] for r in reasons) or "no alert condition met"
    title = f"pinbench: {base.pin} -> {cand.pin} on {manifest.suite_name}"
    flagged = [m for m in verdict.metrics if m.flagged and m.metric in _COST_METRICS]

    lines = [
        f"**{what.capitalize()}** comparing `{base.pin}` with `{cand.pin}`.",
        "",
        f"- Baseline `{base.pin}`: {_pin_line(manifest, base.pin)}",
        f"- Candidate `{cand.pin}`: {_pin_line(manifest, cand.pin)}",
        f"- The pins differ in: {_pin_diff(manifest, base.pin, cand.pin)}",
        f"- Pass rate: {_rate(base)} -> {_rate(cand)}; {verdict.n_discordant} discordant pairs "
        f"({verdict.n_regress} regressed, {verdict.n_improve} improved)",
        f"- Decision: **{verdict.decision}**, E = {verdict.e_value:.3g} against a threshold of "
        f"{1 / verdict.alpha:g}, anytime-valid p <= {verdict.p_value:.3g}",
        f"- Stopped: {verdict.stop_reason} after {verdict.batches_run} batches, "
        f"{'' if verdict.cost_known or not verdict.spent_usd else 'at most '}"
        f"${verdict.spent_usd:.2f} spent",
    ]
    if base.checked or cand.checked:
        lines.append(
            f'- False success ("tests pass" claims the transcript contradicts): '
            f"{base.false_success}/{base.claims} -> {cand.false_success}/{cand.claims}"
        )
    if verdict.metrics:
        lines += ["", "| Metric | Ratio | CI | |", "|---|---|---|---|"]
        lines += [
            f"| {m.metric} | x{m.ratio:.3f} | {m.ci_low:.3f}-{m.ci_high:.3f} | "
            f"{'increase' if m.flagged else ''} |"
            for m in verdict.metrics
        ]
    lines += [
        "",
        f"Run `{manifest.run_id}` (suite commit {(manifest.suite_commit or 'n/a')[:10]}). "
        f"Evidence is in the sealed run bundle: `pinbench report {manifest.run_id}` renders it and "
        f"`pinbench verify {manifest.run_id}` checks its integrity.",
    ]

    slack = [
        f"*{title}*",
        f"{what.capitalize()}: pass rate {_rate(base)} -> {_rate(cand)}, "
        f"p <= {verdict.p_value:.3g} ({verdict.decision})",
    ]
    slack += [f"{m.metric} x{m.ratio:.2f} ({m.ci_low:.2f}-{m.ci_high:.2f})" for m in flagged]
    slack.append(f"run `{manifest.run_id}`, ${verdict.spent_usd:.2f} spent")
    return Alert(
        title=title, reasons=reasons, markdown="\n".join(lines), slack_text="\n".join(slack)
    )


def send_slack(alert: Alert, webhook_url: str, http: Http = https_request) -> str:
    body = json.dumps({"text": alert.slack_text}).encode()
    status, _ = http("POST", webhook_url, {"Content-Type": "application/json"}, body)
    if status != 200:
        raise AlertError(f"Slack webhook returned HTTP {status}")
    return "posted"


def send_github_issue(
    alert: Alert,
    *,
    repo: str,
    token: str,
    labels: list[str],
    api_url: str = "https://api.github.com",
    http: Http = https_request,
) -> str:
    """Open an issue, or comment on the open issue with the same title (one issue per pin pair)."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": _USER_AGENT,
    }
    base = f"{api_url.rstrip('/')}/repos/{repo}/issues"
    query = urllib.parse.urlencode({"state": "open", "labels": ",".join(labels), "per_page": "100"})
    status, raw = http("GET", f"{base}?{query}", headers, None)
    if status != 200:
        raise AlertError(f"GitHub issue search returned HTTP {status}")
    existing = next(
        (i for i in json.loads(raw) if i.get("title") == alert.title and "pull_request" not in i),
        None,
    )
    if existing is not None:
        status, raw = http(
            "POST",
            f"{base}/{existing['number']}/comments",
            headers,
            json.dumps({"body": alert.markdown}).encode(),
        )
        if status != 201:
            raise AlertError(f"GitHub comment returned HTTP {status}")
        return f"commented on #{existing['number']}"
    payload = {"title": alert.title, "body": alert.markdown, "labels": labels}
    status, raw = http("POST", base, headers, json.dumps(payload).encode())
    if status != 201:
        raise AlertError(f"GitHub issue creation returned HTTP {status}")
    return f"opened #{json.loads(raw).get('number')}"


def channels(config: AlertsConfig) -> list[str]:
    return [
        name
        for name, enabled in (("slack", config.slack_webhook_env), ("github", config.github_repo))
        if enabled
    ]


def dispatch(
    config: AlertsConfig,
    alert: Alert,
    env: Mapping[str, str],
    *,
    http: Http = https_request,
) -> list[Delivery]:
    """Send to every configured channel. One channel failing does not stop the others."""
    out: list[Delivery] = []
    sends: list[tuple[str, str, Callable[[str], str]]] = []
    if config.slack_webhook_env:
        sends.append(
            ("slack", config.slack_webhook_env, lambda secret: send_slack(alert, secret, http))
        )
    if config.github_repo:
        repo = config.github_repo
        sends.append(
            (
                "github",
                config.github_token_env,
                lambda secret: send_github_issue(
                    alert,
                    repo=repo,
                    token=secret,
                    labels=config.github_labels,
                    api_url=config.github_api_url,
                    http=http,
                ),
            )
        )
    for channel, env_name, send in sends:
        secret = env.get(env_name)
        if not secret:
            out.append(Delivery(channel, False, f"environment variable {env_name} is not set"))
            continue
        try:
            out.append(Delivery(channel, True, send(secret)))
        except (AlertError, HttpError, ValueError, KeyError) as exc:
            out.append(Delivery(channel, False, str(exc)))
    for d in out:
        log.log(
            logging.INFO if d.ok else logging.WARNING,
            "alert delivery",
            extra={"channel": d.channel, "ok": d.ok, "detail": d.detail},
        )
    return out
