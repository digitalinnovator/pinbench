"""Release watcher, against a fake npm registry. Nothing here touches the network."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from agent_canary import releases
from agent_canary.cli import app
from agent_canary.config import load_config

cli = CliRunner()

# Shape of the real responses on 2026-09-30, shortened.
CLAUDE_TAGS = {"stable": "2.1.280", "latest": "2.1.285", "next": "2.1.285"}
CODEX_TAGS = {"latest": "0.159.2", "alpha": "0.161.0-alpha.3", "linux-x64": "0.159.2-linux-x64"}


def _registry(tags_by_package: dict[str, dict[str, str]], status: int = 200) -> Any:
    def http(
        method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> tuple[int, bytes]:
        assert method == "GET"
        assert body is None
        for package, tags in tags_by_package.items():
            if url == f"https://registry.npmjs.org/-/package/{package}/dist-tags":
                return status, json.dumps(tags).encode()
        return 404, b"{}"

    return http


def test_latest_version_reads_the_dist_tag() -> None:
    http = _registry({"@anthropic-ai%2Fclaude-code": CLAUDE_TAGS, "@openai%2Fcodex": CODEX_TAGS})
    assert releases.latest_version("claude-code", http=http) == "2.1.285"
    assert releases.latest_version("claude-code", "stable", http=http) == "2.1.280"
    assert releases.latest_version("codex", http=http) == "0.159.2"


def test_prereleases_unknown_tags_and_harnesses_are_refused() -> None:
    http = _registry({"@openai%2Fcodex": CODEX_TAGS})
    with pytest.raises(releases.ReleaseError, match="not a plain X"):
        releases.latest_version("codex", "alpha", http=http)
    with pytest.raises(releases.ReleaseError, match="no dist-tag 'nightly'"):
        releases.latest_version("codex", "nightly", http=http)
    with pytest.raises(releases.ReleaseError, match="no release source"):
        releases.latest_version("oracle", http=http)
    with pytest.raises(releases.ReleaseError, match="HTTP 404"):
        releases.latest_version("claude-code", http=http)


def test_versions_compare_numerically() -> None:
    assert releases.version_key("2.1.100") > releases.version_key("2.1.99")


@pytest.fixture
def watched(simulated_project: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The simulated project watching Claude Code, with the registry faked at 1.0.5."""
    toml = simulated_project / "canary.toml"
    toml.write_text(
        toml.read_text()
        + '\n[watch.cc]\nbaseline = "good"\n\n'
        + '[runner.simulated."good-1.0.5"]\npass_rate = 0.30\ncost_usd = 0.60\n'
    )
    tags = {"latest": "1.0.5"}
    monkeypatch.setattr(releases, "https_request", _registry({"@anthropic-ai%2Fclaude-code": tags}))
    yield simulated_project, tags
    for root, _dirs, files in os.walk(simulated_project):
        Path(root).chmod(0o755)
        for f in files:
            (Path(root) / f).chmod(0o644)


def test_candidate_pin_changes_only_the_version(watched: Any) -> None:
    project, _ = watched
    loaded = load_config(project)
    cand = releases.check_watch("cc", loaded.config.watch["cc"], loaded)
    assert (cand.is_new, cand.already_tested, cand.pin_name) == (True, False, "good-1.0.5")
    assert cand.pin.version == "1.0.5"
    assert cand.pin.model_dump(exclude={"version"}) == loaded.pin("good").model_dump(
        exclude={"version"}
    )
    assert loaded.with_pin(cand.pin_name, cand.pin).pin("good-1.0.5") == cand.pin
    assert "good-1.0.5" not in loaded.config.pins


def test_watch_without_run_spends_nothing(watched: Any) -> None:
    project, _ = watched
    result = cli.invoke(app, ["watch", "-c", str(project)], catch_exceptions=False)
    assert result.exit_code == 0
    assert "latest is 1.0.5, baseline good is 1.0.0: NEW RELEASE, not tested" in result.output
    assert not (project / ".canary" / "runs").exists()


def test_watch_run_tests_a_release_once(watched: Any) -> None:
    project, tags = watched
    result = cli.invoke(app, ["watch", "--run", "-c", str(project)], catch_exceptions=False)
    assert result.exit_code == 1, result.output
    assert "REGRESSION" in result.output
    state = json.loads((project / ".canary" / "watch.json").read_text())["cc"]
    assert (state["last_tested"], state["decision"]) == ("1.0.5", "regression")
    (run_dir,) = (project / ".canary" / "runs").iterdir()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert (manifest["baseline"], manifest["candidate"]) == ("good", "good-1.0.5")
    assert state["run_id"] == run_dir.name

    again = cli.invoke(app, ["watch", "--run", "-c", str(project)], catch_exceptions=False)
    assert again.exit_code == 0
    assert "new release already tested" in again.output

    tags["latest"] = "1.0.0"
    same = cli.invoke(app, ["watch", "--run", "-c", str(project)], catch_exceptions=False)
    assert "nothing new" in same.output


def test_watch_config_must_name_a_pin(simulated_project: Path) -> None:
    toml = simulated_project / "canary.toml"
    toml.write_text(toml.read_text() + '\n[watch.cc]\nbaseline = "nope"\n')
    result = cli.invoke(app, ["watch", "-c", str(simulated_project)])
    assert result.exit_code == 2
    assert "unknown baseline pin 'nope'" in result.output


def test_a_release_whose_test_failed_is_not_retried_on_every_tick(watched: Any) -> None:
    project, _ = watched
    toml = project / "canary.toml"
    # Break the run: the derived pin has no simulated arm, so the compare errors out.
    toml.write_text(
        toml.read_text().replace('[runner.simulated."good-1.0.5"]', "[runner.simulated.x]")
    )
    first = cli.invoke(app, ["watch", "--run", "-c", str(project)])
    assert first.exit_code == 2
    state = json.loads((project / ".canary" / "watch.json").read_text())["cc"]
    assert state["last_failed"] == "1.0.5"
    second = cli.invoke(app, ["watch", "--run", "-c", str(project)])
    assert second.exit_code == 2
    assert "an earlier attempt to test this release failed; pass --retest" in second.output
    assert len(list((project / ".canary" / "runs").iterdir())) == 1  # no second attempt
