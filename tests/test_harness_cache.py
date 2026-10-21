from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

from pinbench import harness_cache
from pinbench.harness_cache import HarnessCacheError, ensure_claude_code

PAYLOAD = b"#!/bin/sh\necho 2.1.283 (Claude Code)\n"


class _Resp(io.BytesIO):
    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _fake_urlopen(checksum: str, calls: list[str]) -> Any:
    manifest = {"platforms": {"linux-x64": {"checksum": checksum, "size": len(PAYLOAD)}}}

    def urlopen(url: str, timeout: float) -> _Resp:
        calls.append(url)
        return _Resp(json.dumps(manifest).encode() if url.endswith("manifest.json") else PAYLOAD)

    return urlopen


def test_downloads_verifies_and_reuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    good = hashlib.sha256(PAYLOAD).hexdigest()
    monkeypatch.setattr(harness_cache.urllib.request, "urlopen", _fake_urlopen(good, calls))
    first = ensure_claude_code("2.1.283", tmp_path, "linux-x64")
    assert first.path.read_bytes() == PAYLOAD
    assert first.sha256 == good
    assert first.path.stat().st_mode & 0o777 == 0o555
    downloads = [c for c in calls if c.endswith("/claude")]
    ensure_claude_code("2.1.283", tmp_path, "linux-x64")
    assert [c for c in calls if c.endswith("/claude")] == downloads  # cached: no re-download


def test_checksum_mismatch_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harness_cache.urllib.request, "urlopen", _fake_urlopen("0" * 64, []))
    with pytest.raises(HarnessCacheError, match="checksum mismatch"):
        ensure_claude_code("2.1.283", tmp_path, "linux-x64")
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_missing_platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(harness_cache.urllib.request, "urlopen", _fake_urlopen("0" * 64, []))
    with pytest.raises(HarnessCacheError, match="no linux-arm64 build"):
        ensure_claude_code("2.1.283", tmp_path, "linux-arm64")
