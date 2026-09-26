from __future__ import annotations

import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent_canary.bundle import BundleError, RunBundle, find_bundle, new_run_id
from agent_canary.models import PinRecord, RunManifest, TaskRecord
from agent_canary.store import RunIndex
from tests.conftest import record


def _manifest(run_id: str) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        kind="run",
        created_at=datetime(2026, 9, 27, tzinfo=UTC),
        canary_version="test",
        runner={"kind": "simulated"},
        suite_name="s",
        suite_commit=None,
        suite_dirty=None,
        tasks=[TaskRecord(name="t", digest="d")],
        pins=[PinRecord(name="a", fingerprint="f", spec={"harness": "nop"})],
        settings={},
    )


@pytest.fixture
def bundle(tmp_path: Path) -> RunBundle:
    b = RunBundle.create(tmp_path / "runs", _manifest("20260927T000000Z-run-abc123"))
    b.append_trials([record(task="t", pin="a"), record(task="t", pin="a", batch=1)])
    (b.path / "harbor").mkdir()
    (b.path / "harbor" / "log.txt").write_text("trial output\n")
    return b


def _make_writable(path: Path) -> None:
    for root, _dirs, files in os.walk(path):
        Path(root).chmod(0o755)
        for f in files:
            (Path(root) / f).chmod(0o644)


def test_run_id_format() -> None:
    rid = new_run_id("compare", datetime(2026, 9, 27, 1, 2, 3, tzinfo=UTC))
    assert rid.startswith("20260927T010203Z-compare-")


def test_round_trip_and_seal(bundle: RunBundle) -> None:
    assert [t.batch for t in bundle.trials()] == [0, 1]
    bundle.seal()
    try:
        assert bundle.sealed
        assert bundle.verify() == []
        mode = (bundle.path / "trials.jsonl").stat().st_mode
        assert not mode & stat.S_IWUSR
        with pytest.raises(BundleError, match="sealed"):
            bundle.append_trials([record()])
    finally:
        _make_writable(bundle.path)


def test_verify_detects_tampering(bundle: RunBundle) -> None:
    bundle.seal()
    _make_writable(bundle.path)
    (bundle.path / "harbor" / "log.txt").write_text("edited\n")
    (bundle.path / "harbor" / "extra.txt").write_text("new\n")
    (bundle.path / "manifest.json").unlink()
    assert bundle.verify() == [
        "missing: manifest.json",
        "unexpected: harbor/extra.txt",
        "modified: harbor/log.txt",
    ]


def test_unsealed_bundle_fails_verification(bundle: RunBundle) -> None:
    assert bundle.verify() == ["bundle is not sealed (no SHA256SUMS)"]


def test_find_bundle_by_prefix(bundle: RunBundle, tmp_path: Path) -> None:
    assert find_bundle(tmp_path, "20260927T0000").path == bundle.path
    with pytest.raises(BundleError, match="no run"):
        find_bundle(tmp_path, "1999")


def test_index_ingest_and_rebuild(bundle: RunBundle, tmp_path: Path) -> None:
    index = RunIndex(tmp_path / "index.db")
    index.ingest(bundle)
    index.ingest(bundle)  # idempotent
    rows = index.list_runs()
    assert [r["run_id"] for r in rows] == [bundle.run_id]
    (tmp_path / "index.db").unlink()
    fresh = RunIndex(tmp_path / "index.db")
    assert fresh.rebuild(tmp_path / "runs") == 1
    assert fresh.list_runs()[0]["kind"] == "run"
