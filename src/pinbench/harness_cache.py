"""Host-side cache of pinned harness binaries, mounted read-only into every sandbox.

Without it, Harbor installs the harness inside each sandbox on every trial. For Claude Code that
means downloading a ~240 MB binary twice per trial (the installer fetches `latest`, then the pinned
version), which on a 9 Mbit/s link blew through Harbor's setup timeout (spike 0001). Caching also
means every trial runs byte-identical harness code, verified against the vendor's release manifest.

Only Claude Code's native Linux builds are cached for now.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from pinbench.digest import sha256_file

log = logging.getLogger(__name__)

CLAUDE_RELEASES = "https://downloads.claude.ai/claude-code-releases"
CLAUDE_MOUNT_TARGET = "/usr/local/bin/claude"
_CHUNK = 1 << 20
_TIMEOUT = 60


class HarnessCacheError(RuntimeError):
    pass


@dataclass(frozen=True)
class CachedBinary:
    harness: str
    version: str
    platform: str
    sha256: str
    source_url: str
    path: Path


def default_cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "pinbench" / "harness"


def sandbox_platform() -> str:
    """Docker Desktop runs Linux VMs of the host's architecture."""
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine)
    if arch is None:
        raise HarnessCacheError(f"unsupported host architecture {machine!r}")
    return f"linux-{arch}"


def _fetch_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read())
    if not isinstance(data, dict):
        raise HarnessCacheError(f"unexpected manifest at {url}")
    return data


def ensure_claude_code(version: str, cache_root: Path, plat: str) -> CachedBinary:
    """Return a verified local copy of Claude Code `version`, downloading it once if needed."""
    manifest = _fetch_json(f"{CLAUDE_RELEASES}/{version}/manifest.json")
    platforms = manifest.get("platforms")
    entry = platforms.get(plat) if isinstance(platforms, dict) else None
    if not isinstance(entry, dict) or not isinstance(entry.get("checksum"), str):
        raise HarnessCacheError(f"Claude Code {version} has no {plat} build in its manifest")
    checksum, size = str(entry["checksum"]), int(entry.get("size", 0))
    url = f"{CLAUDE_RELEASES}/{version}/{plat}/claude"
    target = cache_root / "claude-code" / version / plat / "claude"

    if target.exists() and sha256_file(target) == checksum:
        return CachedBinary("claude-code", version, plat, checksum, url, target)

    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(".part")
    log.info("downloading harness binary", extra={"url": url, "mb": round(size / 1e6, 1)})
    digest = hashlib.sha256()
    done, next_report = 0, 0.1
    with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp, part.open("wb") as out:
        while chunk := resp.read(_CHUNK):
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if size and done / size >= next_report:
                log.info("download progress", extra={"percent": round(100 * done / size)})
                next_report += 0.1
    if digest.hexdigest() != checksum:
        part.unlink(missing_ok=True)
        raise HarnessCacheError(f"checksum mismatch for {url}; refusing to use it")
    part.chmod(0o555)
    part.replace(target)
    log.info("harness binary cached", extra={"path": str(target), "sha256": checksum})
    return CachedBinary("claude-code", version, plat, checksum, url, target)
