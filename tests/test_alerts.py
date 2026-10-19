"""Alert building and delivery, against a fake HTTP transport. Nothing here touches the network."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from agent_canary import alerts
from agent_canary.bundle import RunBundle
from agent_canary.cli import app
from agent_canary.config import AlertsConfig, load_config
from agent_canary.http import HttpError, https_request
from agent_canary.orchestrate import run_compare
from agent_canary.runners.simulated import SimulatedRunner
from agent_canary.suite import load_suite

cli = CliRunner()


class FakeHttp:
    def __init__(self, responses: dict[tuple[str, str], tuple[int, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, Mapping[str, str], Any]] = []

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        self.calls.append((method, url, headers, json.loads(body) if body else None))
        for (m, fragment), (status, payload) in self.responses.items():
            if m == method and fragment in url:
                return status, json.dumps(payload).encode()
        return 404, b"{}"


@pytest.fixture
def regression(simulated_project: Path) -> Any:
    loaded = load_config(simulated_project)
    cfg = loaded.config
    runner = SimulatedRunner(
        cfg.runner.simulated, seed=cfg.stats.seed, task_spread=cfg.runner.simulated_task_spread
    )
    outcome = run_compare(loaded, load_suite(loaded), runner, "good", "bad")
    yield outcome.bundle
    for root, _dirs, files in os.walk(simulated_project):
        Path(root).chmod(0o755)
        for f in files:
            (Path(root) / f).chmod(0o644)


def _alert(bundle: RunBundle, on: list[str] | None = None) -> alerts.Alert:
    verdict = bundle.verdict()
    assert verdict is not None
    reasons = alerts.alert_reasons(verdict, on or ["regression"])
    return alerts.build_alert(bundle.manifest(), verdict, reasons)


def test_alert_content(regression: RunBundle) -> None:
    alert = _alert(regression, ["regression", "cost_increase", "false_success"])
    assert alert.reasons == ("regression", "cost_increase")
    assert alert.title == "Agent canary: good -> bad on test-suite"
    assert "claude-code@1.0.1" in alert.markdown
    assert "The pins differ in: version: '1.0.0' -> '1.0.1'" in alert.markdown
    assert "**regression**" in alert.markdown
    assert regression.run_id in alert.markdown
    assert "| cost_usd |" in alert.markdown
    assert alert.slack_text.startswith("*Agent canary: good -> bad on test-suite*")


def test_no_reason_without_a_matching_condition(regression: RunBundle) -> None:
    verdict = regression.verdict()
    assert verdict is not None
    assert alerts.alert_reasons(verdict, ["false_success"]) == ()


def test_slack_posts_text_and_reports_http_errors(regression: RunBundle) -> None:
    http = FakeHttp({("POST", "hooks.slack.test"): (200, "ok")})
    assert alerts.send_slack(_alert(regression), "https://hooks.slack.test/T/B/x", http) == "posted"
    (_, _, _, body) = http.calls[0]
    assert "good -> bad" in body["text"]
    with pytest.raises(alerts.AlertError, match="HTTP 404") as exc:
        alerts.send_slack(_alert(regression), "https://other.test/T/B/secret", http)
    assert "secret" not in str(exc.value)


def test_github_opens_an_issue_then_comments_on_it(regression: RunBundle) -> None:
    alert = _alert(regression)
    send = {"repo": "acme/infra", "token": "t0ken", "labels": ["agent-canary"]}
    http = FakeHttp(
        {("GET", "/repos/acme/infra/issues?"): (200, []), ("POST", "/issues"): (201, {"number": 7})}
    )
    assert alerts.send_github_issue(alert, http=http, **send) == "opened #7"
    method, url, headers, body = http.calls[-1]
    assert (method, url) == ("POST", "https://api.github.com/repos/acme/infra/issues")
    assert headers["Authorization"] == "Bearer t0ken"
    assert body["title"] == alert.title
    assert body["labels"] == ["agent-canary"]

    existing = [
        {"number": 3, "title": alert.title, "pull_request": {}},
        {"number": 7, "title": alert.title},
    ]
    http = FakeHttp(
        {
            ("GET", "/repos/acme/infra/issues?"): (200, existing),
            ("POST", "/issues/7/comments"): (201, {}),
        }
    )
    assert alerts.send_github_issue(alert, http=http, **send) == "commented on #7"
    assert http.calls[-1][1].endswith("/issues/7/comments")


def test_dispatch_isolates_failures_and_missing_secrets(regression: RunBundle) -> None:
    config = AlertsConfig(slack_webhook_env="CANARY_SLACK", github_repo="acme/infra")
    http = FakeHttp({("POST", "hooks.slack.test"): (200, "ok")})
    env = {"CANARY_SLACK": "https://hooks.slack.test/x"}
    slack, github = alerts.dispatch(config, _alert(regression), env, http=http)
    assert (slack.channel, slack.ok) == ("slack", True)
    assert (github.ok, github.detail) == (False, "environment variable GITHUB_TOKEN is not set")

    slack, github = alerts.dispatch(
        config, _alert(regression), {**env, "GITHUB_TOKEN": "t"}, http=http
    )
    assert slack.ok
    assert (github.ok, github.detail) == (False, "GitHub issue search returned HTTP 404")


def test_default_transport_refuses_plain_http() -> None:
    with pytest.raises(HttpError, match="https"):
        https_request("POST", "http://example.test/hook", {}, b"{}")
    with pytest.raises(HttpError, match="https"):
        https_request("GET", "file:///etc/passwd", {}, None)


def test_config_rejects_secrets_in_place_of_env_names() -> None:
    with pytest.raises(ValueError, match="NAME of an environment variable"):
        AlertsConfig(slack_webhook_env="https://hooks.slack.com/services/T/B/x")
    with pytest.raises(ValueError, match="owner/name"):
        AlertsConfig(github_repo="https://github.com/acme/infra")


def test_cli_dry_run_prints_and_sends_nothing(
    regression: RunBundle, simulated_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_: Any, **__: Any) -> Any:
        raise AssertionError("dry run must not send")

    monkeypatch.setattr(alerts, "dispatch", _boom)
    result = cli.invoke(
        app,
        ["alert", regression.run_id, "-c", str(simulated_project), "--dry-run"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "channels: (none configured)" in result.output
    assert "title: Agent canary: good -> bad on test-suite" in result.output


def test_compare_alerts_when_configured_and_survives_failed_delivery(
    simulated_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    toml = simulated_project / "canary.toml"
    toml.write_text(toml.read_text() + '\n[alerts]\nslack_webhook_env = "CANARY_SLACK"\n')
    monkeypatch.delenv("CANARY_SLACK", raising=False)
    try:
        result = cli.invoke(
            app,
            ["compare", "good", "bad", "-c", str(simulated_project), "--no-report"],
            catch_exceptions=False,
        )
    finally:
        for root, _dirs, files in os.walk(simulated_project):
            Path(root).chmod(0o755)
            for f in files:
                (Path(root) / f).chmod(0o644)
    assert result.exit_code == 1  # the regression, not the failed alert
    assert "alert slack: environment variable CANARY_SLACK is not set" in result.output
