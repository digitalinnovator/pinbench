"""Immutable run bundles: the canary's system of record (ADR-0004)."""

from __future__ import annotations

import os
import secrets
import stat
from datetime import UTC, datetime
from pathlib import Path

from agent_canary.digest import iter_files, sha256_file
from agent_canary.models import RunManifest, TrialRecord, Verdict

MANIFEST = "manifest.json"
TRIALS = "trials.jsonl"
VERDICT = "verdict.json"
CHECKSUMS = "SHA256SUMS"

_READ_ONLY_FILE = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
_READ_ONLY_DIR = _READ_ONLY_FILE | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


class BundleError(RuntimeError):
    pass


def new_run_id(kind: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    return f"{now:%Y%m%dT%H%M%SZ}-{kind}-{secrets.token_hex(3)}"


class RunBundle:
    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def run_id(self) -> str:
        return self.path.name

    @property
    def sealed(self) -> bool:
        return (self.path / CHECKSUMS).exists()

    # -- writing ------------------------------------------------------------------------------

    @classmethod
    def create(cls, runs_dir: Path, manifest: RunManifest) -> RunBundle:
        path = runs_dir / manifest.run_id
        path.mkdir(parents=True, exist_ok=False)
        bundle = cls(path)
        (path / MANIFEST).write_text(manifest.model_dump_json(indent=2) + "\n")
        (path / TRIALS).touch()
        return bundle

    def _assert_writable(self) -> None:
        if self.sealed:
            raise BundleError(f"bundle {self.run_id} is sealed")

    def append_trials(self, records: list[TrialRecord]) -> None:
        self._assert_writable()
        with (self.path / TRIALS).open("a") as f:
            for r in records:
                f.write(r.model_dump_json() + "\n")

    def write_verdict(self, verdict: Verdict) -> None:
        self._assert_writable()
        (self.path / VERDICT).write_text(verdict.model_dump_json(indent=2) + "\n")

    def seal(self) -> None:
        """Write checksums for every file, then make the whole tree read-only."""
        self._assert_writable()
        lines = [
            f"{sha256_file(p)}  {p.relative_to(self.path).as_posix()}"
            for p in iter_files(self.path)
        ]
        (self.path / CHECKSUMS).write_text("\n".join(lines) + "\n")
        for root, dirs, files in os.walk(self.path, topdown=False):
            for name in files:
                full = Path(root) / name
                if not full.is_symlink():
                    full.chmod(_READ_ONLY_FILE)
            for name in dirs:
                full = Path(root) / name
                if not full.is_symlink():
                    full.chmod(_READ_ONLY_DIR)
        self.path.chmod(_READ_ONLY_DIR)

    # -- reading ------------------------------------------------------------------------------

    def manifest(self) -> RunManifest:
        return RunManifest.model_validate_json((self.path / MANIFEST).read_text())

    def trials(self) -> list[TrialRecord]:
        text = (self.path / TRIALS).read_text()
        return [TrialRecord.model_validate_json(line) for line in text.splitlines() if line]

    def verdict(self) -> Verdict | None:
        path = self.path / VERDICT
        return Verdict.model_validate_json(path.read_text()) if path.exists() else None

    def verify(self) -> list[str]:
        """Recompute checksums. Returns a list of problems; empty means intact."""
        sums_path = self.path / CHECKSUMS
        if not sums_path.exists():
            return ["bundle is not sealed (no SHA256SUMS)"]
        expected: dict[str, str] = {}
        for line in sums_path.read_text().splitlines():
            digest, _, rel = line.partition("  ")
            expected[rel] = digest
        actual = {
            p.relative_to(self.path).as_posix(): p
            for p in iter_files(self.path)
            if p.name != CHECKSUMS
        }
        problems = [f"missing: {rel}" for rel in sorted(set(expected) - set(actual))]
        problems += [f"unexpected: {rel}" for rel in sorted(set(actual) - set(expected))]
        problems += [
            f"modified: {rel}"
            for rel in sorted(set(expected) & set(actual))
            if sha256_file(actual[rel]) != expected[rel]
        ]
        return problems


def runs_dir(home: Path) -> Path:
    return home / "runs"


def find_bundle(home: Path, run_id: str) -> RunBundle:
    root = runs_dir(home)
    exact = root / run_id
    if exact.is_dir():
        return RunBundle(exact)
    matches = sorted(p for p in root.glob(f"{run_id}*") if p.is_dir()) if root.is_dir() else []
    if len(matches) == 1:
        return RunBundle(matches[0])
    if not matches:
        raise BundleError(f"no run matching {run_id!r} under {root}")
    raise BundleError(f"{run_id!r} is ambiguous: {', '.join(m.name for m in matches)}")
