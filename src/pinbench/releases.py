"""Release watcher: detect a new harness version and derive the pin to test it with.

The npm dist-tags endpoint is tiny and needs no auth; see the harness-telemetry research note.
Only plain `X.Y.Z` versions are accepted, which skips alpha, beta, snapshot and per-platform tags.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pinbench.config import LoadedConfig, PinSpec, WatchConfig
from pinbench.http import Http, HttpError, https_request

NPM_REGISTRY = "https://registry.npmjs.org"
NPM_PACKAGES = {
    "claude-code": "@anthropic-ai/claude-code",
    "codex": "@openai/codex",
    "opencode": "opencode-ai",
}
STATE_FILE = "watch.json"

_STABLE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class ReleaseError(RuntimeError):
    pass


def version_key(version: str) -> tuple[int, int, int]:
    match = _STABLE.match(version)
    if not match:
        raise ReleaseError(f"{version!r} is not a plain X.Y.Z version")
    major, minor, patch = (int(g) for g in match.groups())
    return major, minor, patch


def latest_version(harness: str, channel: str = "latest", http: Http | None = None) -> str:
    """The version an npm dist-tag points at right now."""
    http = http or https_request
    package = NPM_PACKAGES.get(harness)
    if package is None:
        raise ReleaseError(
            f"no release source for harness {harness!r}; known: {', '.join(sorted(NPM_PACKAGES))}"
        )
    url = f"{NPM_REGISTRY}/-/package/{urllib.parse.quote(package, safe='@')}/dist-tags"
    try:
        status, raw = http("GET", url, {"Accept": "application/json"}, None)
    except HttpError as exc:
        raise ReleaseError(f"could not reach the npm registry: {exc}") from None
    if status != 200:
        raise ReleaseError(f"npm dist-tags for {package} returned HTTP {status}")
    try:
        tags = json.loads(raw)
    except ValueError:
        raise ReleaseError(f"npm dist-tags for {package} is not JSON") from None
    version = tags.get(channel) if isinstance(tags, dict) else None
    if not isinstance(version, str):
        raise ReleaseError(f"{package} has no dist-tag {channel!r}")
    version_key(version)  # a tag pointing at a pre-release is refused, not tested
    return version


@dataclass(frozen=True)
class Candidate:
    watch: str
    baseline: str
    baseline_version: str
    latest: str
    pin_name: str
    pin: PinSpec
    already_tested: bool
    failed_before: bool = False

    @property
    def is_new(self) -> bool:
        return version_key(self.latest) > version_key(self.baseline_version)


def check_watch(
    name: str, watch: WatchConfig, loaded: LoadedConfig, http: Http | None = None
) -> Candidate:
    """Compare the channel's current version with the baseline pin's version."""
    baseline = loaded.pin(watch.baseline)
    if not baseline.version:
        raise ReleaseError(f"watch {name!r}: pin {watch.baseline!r} has no version to compare")
    latest = latest_version(baseline.harness, watch.channel, http)
    version_key(baseline.version)
    state = read_state(loaded.home).get(name, {})
    return Candidate(
        watch=name,
        baseline=watch.baseline,
        baseline_version=baseline.version,
        latest=latest,
        pin_name=f"{watch.baseline}-{latest}",
        # Everything but the version is held fixed, so a verdict is attributable to the release.
        pin=baseline.model_copy(update={"version": latest}),
        already_tested=state.get("last_tested") == latest,
        failed_before=state.get("last_failed") == latest,
    )


def read_state(home: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads((home / STATE_FILE).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(home: Path, state: dict[str, dict[str, Any]]) -> None:
    home.mkdir(parents=True, exist_ok=True)
    tmp = home / f"{STATE_FILE}.tmp"
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    tmp.replace(home / STATE_FILE)


def record_failed(home: Path, watch: str, version: str) -> None:
    """Remember a release whose test could not complete, so a schedule does not retry it blindly."""
    state = read_state(home)
    state[watch] = {
        **state.get(watch, {}),
        "last_failed": version,
        "failed_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _write_state(home, state)


def record_tested(home: Path, watch: str, version: str, run_id: str, decision: str) -> None:
    """Remember that a release was tested, so the next scheduled check does not pay for it again."""
    state = read_state(home)
    state[watch] = {
        "last_tested": version,
        "run_id": run_id,
        "decision": decision,
        "tested_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    _write_state(home, state)
