"""HarborRunner's job planning and process handling, against a fake Harbor CLI (no Docker)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from pinbench.config import PinSpec, RunnerConfig
from pinbench.harness_cache import CachedBinary
from pinbench.runners import BatchRequest
from pinbench.runners import harbor as harbor_module
from pinbench.runners.harbor import HarborRunner
from pinbench.suite import TaskRef
from tests.conftest import write_task

FAKE_HARBOR = [sys.executable, str(Path(__file__).parent / "fake_harbor.py")]


def _cc(version: str, **options: str) -> PinSpec:
    return PinSpec(harness="claude-code", version=version, model="m", options=options)


@pytest.fixture
def fake_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    """Replace the binary download with a stub and record which versions were requested."""
    requested: list[str] = []

    def ensure(version: str, root: Path, plat: str) -> CachedBinary:
        requested.append(version)
        path = tmp_path / "cache" / version / "claude"
        return CachedBinary("claude-code", version, plat, "0" * 64, "https://example.test", path)

    monkeypatch.setattr(harbor_module, "ensure_claude_code", ensure)
    monkeypatch.setattr(harbor_module, "sandbox_platform", lambda: "linux-x64")
    return requested


def _request(tmp_path: Path, pins: dict[str, PinSpec]) -> BatchRequest:
    tasks = tuple(
        TaskRef(name=n, path=write_task(tmp_path / "tasks", n), digest="d") for n in ("a", "b")
    )
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    return BatchRequest(batch=0, tasks=tasks, pins=pins, attempts=1, bundle_dir=bundle)


def _runner(tmp_path: Path, **overrides: object) -> HarborRunner:
    config = RunnerConfig(harbor_command=FAKE_HARBOR, n_concurrent=4, **overrides)  # type: ignore[arg-type]
    return HarborRunner(config, cwd=tmp_path, pass_threshold=1.0)


def _configs(bundle: Path) -> dict[str, dict[str, object]]:
    return {
        p.stem: yaml.safe_load(p.read_text())
        for p in sorted((bundle / "harbor-configs").glob("*.yaml"))
    }


def test_same_version_pins_share_one_job_and_one_mount(
    tmp_path: Path, fake_cache: list[str]
) -> None:
    pins = {"high": _cc("2.1.283", effort="high"), "low": _cc("2.1.283", effort="low")}
    request = _request(tmp_path, pins)
    records = _runner(tmp_path).run_batch(request)
    assert sorted((r.task, r.pin) for r in records) == [
        ("a", "high"),
        ("a", "low"),
        ("b", "high"),
        ("b", "low"),
    ]
    (name, config) = _configs(request.bundle_dir).popitem()
    assert name == "batch-000"
    assert config["n_concurrent_trials"] == 4
    assert len(config["agents"]) == 2  # type: ignore[arg-type]
    assert fake_cache == ["2.1.283"]


def test_different_versions_get_one_job_each_with_their_own_binary(
    tmp_path: Path, fake_cache: list[str]
) -> None:
    pins = {
        "old": _cc("2.1.283"),
        "new": _cc("2.1.285"),
        "oracle": PinSpec(harness="oracle"),
    }
    request = _request(tmp_path, pins)
    records = _runner(tmp_path).run_batch(request)
    assert len(records) == 6
    assert {r.pin for r in records} == {"old", "new", "oracle"}

    configs = _configs(request.bundle_dir)
    assert sorted(configs) == ["batch-000-cc2.1.283", "batch-000-cc2.1.285"]
    for version in ("2.1.283", "2.1.285"):
        config = configs[f"batch-000-cc{version}"]
        (mount,) = config["environment"]["mounts"]  # type: ignore[index]
        assert mount["source"].endswith(f"cache/{version}/claude")
        assert mount["read_only"] is True
        assert config["n_concurrent_trials"] == 2  # the batch's budget of 4, shared by 2 jobs
        provenance = request.bundle_dir / "harbor-configs" / f"batch-000-cc{version}.harness.json"
        assert f'"version": "{version}"' in provenance.read_text()
    names = [[a["name"] for a in c["agents"]] for c in configs.values()]  # type: ignore[union-attr,index]
    assert names == [["claude-code", "oracle"], ["claude-code"]]
    assert sorted(fake_cache) == ["2.1.283", "2.1.285"]


def test_without_the_cache_versions_stay_in_one_job(tmp_path: Path, fake_cache: list[str]) -> None:
    request = _request(tmp_path, {"old": _cc("2.1.283"), "new": _cc("2.1.285")})
    records = _runner(tmp_path, harness_cache=False).run_batch(request)
    assert len(records) == 4
    assert list(_configs(request.bundle_dir)) == ["batch-000"]
    assert fake_cache == []
