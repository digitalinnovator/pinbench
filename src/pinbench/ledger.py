"""Campaign ledger: a lifetime spending limit per credit pool, across every run (ADR-0009).

`[budget] max_usd` stops one compare run, softly, from the average batch cost so far. It cannot
bound the first batch, a second invocation, `pinbench run`, or a scheduled `pinbench watch`. The
ledger can: before any batch that spends money pinbench reserves the batch's worst case
(trials x per-trial cap) against a limit the operator set for that pool, and refuses to start if
the reservation does not fit. After the batch the reservation is settled to what the batch
actually cost. A batch that crashes stays reserved at its worst case, so an interrupted run can
never make the ledger under-count.

The ledger is an append-only JSON-lines file per pool, outside every suite's `.pinbench`, guarded
by a file lock so concurrent runs cannot both take the last dollars.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ENV_DIR = "PINBENCH_LEDGER_DIR"
_EPSILON = 1e-9


class LedgerError(RuntimeError):
    """The ledger refused a reservation, or has no limit for the pool."""


def default_ledger_dir() -> Path:
    override = os.environ.get(ENV_DIR)
    if override:
        return Path(override)
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "pinbench" / "ledger"


@dataclass(frozen=True)
class PoolStatus:
    pool: str
    limit_usd: float | None
    settled_usd: float  # actual cost of settled batches, plus corrections
    reserved_usd: float  # worst case of batches that never settled (running or crashed)

    @property
    def committed_usd(self) -> float:
        return self.settled_usd + self.reserved_usd

    @property
    def remaining_usd(self) -> float | None:
        return None if self.limit_usd is None else self.limit_usd - self.committed_usd


@dataclass(frozen=True)
class Reservation:
    pool: str
    id: str
    usd: float


def _amount(value: Any, what: str) -> float:
    """A finite dollar amount. NaN or infinity would make every later comparison pass."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise LedgerError(f"{what} is not a number: {value!r}") from None
    if not math.isfinite(amount):
        raise LedgerError(f"{what} must be a finite number, not {value!r}")
    return amount


class Ledger:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or default_ledger_dir()

    def _path(self, pool: str) -> Path:
        if not pool.replace("-", "").replace("_", "").isalnum():
            raise LedgerError(f"invalid pool name {pool!r}")
        return self.directory / f"{pool}.jsonl"

    @contextmanager
    def _locked(self, pool: str) -> Iterator[Path]:
        """Exclusive lock for a read-decide-append cycle on one pool."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self._path(pool)
        with (self.directory / f"{pool}.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield path
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    @staticmethod
    def _read(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        entries = []
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                # A ledger that cannot be read must stop spending, not reset to zero.
                raise LedgerError(f"{path}:{number} is not valid JSON; fix it by hand") from None
            if not isinstance(entry, dict) or "type" not in entry:
                raise LedgerError(f"{path}:{number} is not a ledger entry; fix it by hand")
            if "usd" in entry:
                entry["usd"] = _amount(entry["usd"], f"{path}:{number} usd")
            entries.append(entry)
        return entries

    @staticmethod
    def _append(path: Path, entry: dict[str, Any]) -> None:
        entry = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), **entry}
        # If a crash left a partial last line, start on a fresh one: the torn line then fails to
        # parse on its own (which stops spending) instead of swallowing this record too.
        torn = path.exists() and path.stat().st_size > 0 and not path.read_bytes().endswith(b"\n")
        with path.open("a") as f:
            f.write(("\n" if torn else "") + json.dumps(entry, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def _status(pool: str, entries: list[dict[str, Any]]) -> PoolStatus:
        limit: float | None = None
        settled = 0.0
        open_reservations: dict[str, float] = {}
        for e in entries:
            kind = e.get("type")
            if kind == "limit":
                limit = float(e["usd"])
            elif kind == "reserve":
                open_reservations[e["id"]] = float(e["usd"])
            elif kind == "settle":
                open_reservations.pop(e["id"], None)
                settled += float(e["usd"])
            elif kind == "correct":
                settled += float(e["usd"])
        return PoolStatus(pool, limit, settled, sum(open_reservations.values()))

    # -- public API ---------------------------------------------------------------------------

    def status(self, pool: str) -> PoolStatus:
        with self._locked(pool) as path:
            return self._status(pool, self._read(path))

    def pools(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(p.stem for p in self.directory.glob("*.jsonl"))

    def set_limit(
        self, pool: str, usd: float, note: str = "", *, if_unset: bool = False
    ) -> PoolStatus:
        usd = _amount(usd, "the limit")
        if usd < 0:
            raise LedgerError("a limit cannot be negative")
        with self._locked(pool) as path:
            current = self._status(pool, self._read(path))
            if if_unset and current.limit_usd is not None:
                return current
            self._append(path, {"type": "limit", "pool": pool, "usd": usd, "note": note})
            return self._status(pool, self._read(path))

    def reserve(
        self, pool: str, usd: float, *, run_id: str, batch: int, note: str = ""
    ) -> Reservation:
        """Set aside a batch's worst case, or raise LedgerError if it does not fit the limit."""
        usd = _amount(usd, "the reservation")
        if usd < 0:
            raise LedgerError("a reservation cannot be negative")
        with self._locked(pool) as path:
            status = self._status(pool, self._read(path))
            if status.limit_usd is None:
                raise LedgerError(
                    f"no spending limit is set for the {pool!r} pool; set one with "
                    f"`pinbench ledger limit {pool} <usd>` before running a paid harness"
                )
            if status.committed_usd + usd > status.limit_usd + _EPSILON:
                raise LedgerError(
                    f"the {pool!r} ledger refuses this batch: it could cost ${usd:.2f} "
                    f"(every trial at its cap), ${status.committed_usd:.2f} of the "
                    f"${status.limit_usd:.2f} limit is already committed "
                    f"(${status.settled_usd:.2f} spent, ${status.reserved_usd:.2f} held for "
                    "batches that never settled)"
                )
            reservation = Reservation(pool, secrets.token_hex(6), usd)
            self._append(
                path,
                {
                    "type": "reserve",
                    "pool": pool,
                    "id": reservation.id,
                    "usd": usd,
                    "run_id": run_id,
                    "batch": batch,
                    "note": note,
                },
            )
            return reservation

    def settle(self, reservation: Reservation, actual_usd: float, note: str = "") -> None:
        """Replace a reservation with what the batch actually cost."""
        actual_usd = _amount(actual_usd, "the settled amount")
        with self._locked(reservation.pool) as path:
            self._append(
                path,
                {
                    "type": "settle",
                    "pool": reservation.pool,
                    "id": reservation.id,
                    "usd": max(actual_usd, 0.0),
                    "reserved_usd": reservation.usd,
                    "note": note,
                },
            )

    def correct(self, pool: str, usd: float, note: str) -> PoolStatus:
        """Add (or, if negative, remove) dollars so the ledger matches the provider's console."""
        usd = _amount(usd, "the correction")
        with self._locked(pool) as path:
            self._append(path, {"type": "correct", "pool": pool, "usd": usd, "note": note})
            return self._status(pool, self._read(path))

    def open_reservations(self, pool: str) -> list[dict[str, Any]]:
        """Reservations that never settled: batches still running, or that crashed."""
        with self._locked(pool) as path:
            return self._open(self._read(path))

    @staticmethod
    def _open(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        held: dict[str, dict[str, Any]] = {}
        for e in entries:
            if e.get("type") == "reserve":
                held[e["id"]] = e
            elif e.get("type") == "settle":
                held.pop(e["id"], None)
        return list(held.values())

    def release(
        self, pool: str, run_id: str, actual_usd: float, note: str, *, min_age_sec: float = 0.0
    ) -> list[dict[str, Any]]:
        """Settle one run's open reservations at what the console shows that run cost.

        Only for a run that has certainly stopped. Releasing a batch that is still running would
        hand its worst case to another run while it keeps spending, so a young reservation is
        refused unless the caller overrides the age check.
        """
        actual_usd = _amount(actual_usd, "the released amount")
        if actual_usd < 0:
            raise LedgerError("the released amount cannot be negative")
        with self._locked(pool) as path:
            mine = [e for e in self._open(self._read(path)) if e.get("run_id") == run_id]
            if not mine:
                raise LedgerError(f"no open reservation for run {run_id!r} in the {pool!r} pool")
            now = datetime.now(UTC)
            for e in mine:
                age = (now - datetime.fromisoformat(e["ts"])).total_seconds()
                if age < min_age_sec:
                    raise LedgerError(
                        f"the reservation for run {run_id!r} batch {e.get('batch')} is only "
                        f"{age / 60:.0f} minutes old; its batch may still be running and "
                        "spending. Wait, or pass --force if the process is certainly dead"
                    )
            for i, e in enumerate(mine):
                self._append(
                    path,
                    {
                        "type": "settle",
                        "pool": pool,
                        "id": e["id"],
                        "usd": actual_usd if i == 0 else 0.0,
                        "reserved_usd": e["usd"],
                        "note": note,
                    },
                )
            return mine
