"""SQLite run index. Derived from bundles and rebuildable at any time (ADR-0004)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from agent_canary.bundle import RunBundle

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    suite_name    TEXT NOT NULL,
    suite_commit  TEXT,
    baseline      TEXT,
    candidate     TEXT,
    decision      TEXT,
    stop_reason   TEXT,
    e_value       REAL,
    p_value       REAL,
    spent_usd     REAL,
    bundle_path   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pins (
    run_id        TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    fingerprint   TEXT NOT NULL,
    harness       TEXT NOT NULL,
    version       TEXT,
    model         TEXT,
    PRIMARY KEY (run_id, name)
);
CREATE TABLE IF NOT EXISTS trials (
    run_id            TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    trial_name        TEXT NOT NULL,
    task              TEXT NOT NULL,
    pin               TEXT NOT NULL,
    batch             INTEGER NOT NULL,
    status            TEXT NOT NULL,
    reward            REAL,
    n_input_tokens    INTEGER,
    n_cache_tokens    INTEGER,
    n_output_tokens   INTEGER,
    reported_cost_usd REAL,
    agent_seconds     REAL,
    installed_version TEXT,
    exception_type    TEXT,
    PRIMARY KEY (run_id, trial_name)
);
CREATE INDEX IF NOT EXISTS trials_by_pin ON trials (pin, task);
"""


class RunIndex:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def ingest(self, bundle: RunBundle) -> None:
        m = bundle.manifest()
        v = bundle.verdict()
        with self._connect() as db:
            db.execute("DELETE FROM runs WHERE run_id = ?", (m.run_id,))
            db.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    m.run_id,
                    m.kind,
                    m.created_at.isoformat(),
                    m.suite_name,
                    m.suite_commit,
                    m.baseline,
                    m.candidate,
                    v.decision if v else None,
                    v.stop_reason if v else None,
                    v.e_value if v else None,
                    v.p_value if v else None,
                    v.spent_usd if v else None,
                    str(bundle.path),
                ),
            )
            db.executemany(
                "INSERT INTO pins VALUES (?,?,?,?,?,?)",
                [
                    (
                        m.run_id,
                        p.name,
                        p.fingerprint,
                        p.spec.get("harness"),
                        p.spec.get("version"),
                        p.spec.get("model"),
                    )
                    for p in m.pins
                ],
            )
            db.executemany(
                "INSERT INTO trials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        m.run_id,
                        t.trial_name,
                        t.task,
                        t.pin,
                        t.batch,
                        t.status.value,
                        t.reward,
                        t.n_input_tokens,
                        t.n_cache_tokens,
                        t.n_output_tokens,
                        t.reported_cost_usd,
                        t.agent_seconds,
                        t.installed_version,
                        t.exception_type,
                    )
                    for t in bundle.trials()
                ],
            )

    def rebuild(self, runs_root: Path) -> int:
        with self._connect() as db:
            db.execute("DELETE FROM runs")
        count = 0
        for path in (
            sorted(p for p in runs_root.glob("*") if p.is_dir()) if runs_root.is_dir() else []
        ):
            self.ingest(RunBundle(path))
            count += 1
        return count

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
