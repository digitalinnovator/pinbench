"""What a batch can cost at worst, and how the campaign ledger is charged for it (ADR-0009).

Two bounds work together. `[budget] max_usd` is a soft stop on one compare run, from measured
spend. The ledger is the hard one: before every batch that spends money, the batch's worst case
(every trial at its per-trial cap) is reserved against a lifetime limit per credit pool, and
afterwards settled to what the batch cost. Unknown costs are charged at the cap, never at zero.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from pinbench.config import LoadedConfig, PinSpec
from pinbench.ledger import Ledger, LedgerError, Reservation
from pinbench.models import TrialRecord, TrialStatus
from pinbench.pricing import one_request_usd
from pinbench.runners import Runner

log = logging.getLogger(__name__)


class BudgetError(RuntimeError):
    """A run was refused before spending anything."""


def trial_cost(record: TrialRecord) -> float | None:
    """The higher of the two cost estimates, so a stale price table can never hide spend."""
    known = [c for c in (record.reported_cost_usd, record.cost_usd) if c is not None]
    return max(known) if known else None


@dataclass(frozen=True)
class BatchPlan:
    """The worst case of one batch: every task, `attempts` times, on every pin."""

    trials_per_pin: int
    caps: dict[str, float]  # pin name -> worst-case dollars per trial
    pools: dict[str, str | None]  # pin name -> credit pool (None: free)
    paid: bool  # False for simulated and fake runners: nothing is reserved

    @property
    def trials(self) -> int:
        return self.trials_per_pin * len(self.caps)

    @property
    def worst_case_usd(self) -> float:
        return sum(self.trials_per_pin * cap for cap in self.caps.values())

    def reservations(self) -> dict[str, float]:
        """Worst-case dollars per pool for one batch."""
        out: dict[str, float] = defaultdict(float)
        for pin, cap in self.caps.items():
            pool = self.pools[pin]
            if pool is not None:
                out[pool] += self.trials_per_pin * cap
        return dict(out)

    def charge(self, record: TrialRecord) -> float:
        """Dollars to count for one trial: its known cost, or its cap if the cost is unknown.

        An infrastructure error with no cost is charged at the cap too. That over-counts a trial
        that failed before any API call, and it is the safe direction: the alternative let a
        batch of failed-but-billed trials count as free.
        """
        cost = trial_cost(record)
        return cost if cost is not None else self.caps.get(record.pin, 0.0)

    def spent(self, records: list[TrialRecord]) -> tuple[float, bool]:
        """(dollars charged, whether every trial had a real cost).

        The dollars are an upper bound whenever the flag is False: some trial was charged at its
        cap, which is right for stopping a run and wrong as a measurement.
        """
        known = all(trial_cost(r) is not None for r in records)
        return sum(self.charge(r) for r in records), known

    def actual_by_pool(self, records: list[TrialRecord]) -> dict[str, float]:
        """What a finished batch is settled at: charges, plus the cap for every missing trial."""
        out: dict[str, float] = defaultdict(float)
        seen: dict[str, set[str]] = defaultdict(set)
        for r in records:
            if r.trial_name in seen[r.pin]:
                continue  # a duplicated record must not hide a missing trial
            seen[r.pin].add(r.trial_name)
            pool = self.pools.get(r.pin)
            if pool is not None:
                out[pool] += self.charge(r)
        for pin, cap in self.caps.items():
            pool = self.pools[pin]
            missing = self.trials_per_pin - len(seen[pin])
            if pool is not None and missing > 0:
                out[pool] += missing * cap
        return dict(out)


def pin_cap_usd(loaded: LoadedConfig, pin: PinSpec) -> float | None:
    """Worst-case dollars for one trial of a pin, or None if nothing enforces a bound.

    For Claude Code this is its own cap plus an allowance for the request in flight when the cap
    is crossed: the larger of the configured floor and one typical request at the model's
    prices. A model missing from the price table has no such estimate, so the pin must then say
    what to reserve.
    """
    allowance = loaded.config.budget.inflight_allowance_usd
    if pin.harness_cap_usd() is not None:
        one_request = one_request_usd(pin.model)
        if one_request is None and pin.reserve_usd is None:
            return None
        allowance = max(allowance, one_request or 0.0)
    return pin.trial_cap_usd(allowance)


def plan_batch(
    loaded: LoadedConfig, runner: Runner, pins: dict[str, PinSpec], n_tasks: int, attempts: int
) -> BatchPlan:
    """Work out per-trial caps, refusing a paid pin that nothing bounds."""
    paid = bool(getattr(runner, "spends_money", False))
    caps: dict[str, float] = {}
    pools: dict[str, str | None] = {}
    for name, pin in pins.items():
        pool = pin.pool() if paid else None
        cap = pin_cap_usd(loaded, pin)
        if pool is not None and cap is None:
            raise BudgetError(
                f"pin {name!r} has no enforced per-trial spending bound. Claude Code needs "
                "options.max_budget_usd (and reserve_usd if its model is not in the price table). "
                "A harness with no dollar cap needs both timeout_sec and reserve_usd"
            )
        pools[name] = pool
        caps[name] = cap if (cap is not None and pool is not None) else 0.0
    return BatchPlan(trials_per_pin=n_tasks * attempts, caps=caps, pools=pools, paid=paid)


def ledger_for(loaded: LoadedConfig | None = None) -> Ledger:
    """The one campaign ledger. It is deliberately not configurable per suite: a ledger per
    suite would give each suite its own limit and no limit overall."""
    return Ledger()


def preflight(plan: BatchPlan, ledger: Ledger, *, max_usd: float | None = None) -> None:
    """Refuse before anything is created if the first batch cannot be reserved."""
    if plan.paid and max_usd is not None and plan.worst_case_usd > max_usd + 1e-9:
        raise BudgetError(
            f"one batch could cost ${plan.worst_case_usd:.2f} ({plan.trials} trials at their "
            f"caps), which is more than max_usd ${max_usd:.2f}. Lower the per-trial caps, run "
            "fewer tasks, or raise max_usd"
        )
    for pool, usd in plan.reservations().items():
        status = ledger.status(pool)
        if status.limit_usd is None:
            raise BudgetError(
                f"no spending limit is set for the {pool!r} pool; set one with "
                f"`pinbench ledger limit {pool} <usd>` before running a paid harness"
            )
        if status.committed_usd + usd > status.limit_usd + 1e-9:
            raise BudgetError(
                f"the {pool!r} ledger has ${status.limit_usd - status.committed_usd:.2f} left of "
                f"${status.limit_usd:.2f}, and one batch could cost ${usd:.2f} "
                f"({plan.trials} trials at their caps)"
            )


@dataclass
class BatchCharge:
    """Reservations held for one running batch. Left open if the batch crashes."""

    ledger: Ledger
    plan: BatchPlan
    held: list[Reservation] = field(default_factory=list)

    @classmethod
    def reserve(cls, ledger: Ledger, plan: BatchPlan, *, run_id: str, batch: int) -> BatchCharge:
        charge = cls(ledger, plan)
        try:
            for pool, usd in plan.reservations().items():
                charge.held.append(ledger.reserve(pool, usd, run_id=run_id, batch=batch))
        except LedgerError:
            charge.cancel()
            raise
        return charge

    def cancel(self) -> None:
        """Release reservations for a batch that never started."""
        for r in self.held:
            self.ledger.settle(r, 0.0, note="batch did not start")
        self.held.clear()

    def settle(self, records: list[TrialRecord]) -> None:
        actual = self.plan.actual_by_pool(records)
        for r in self.held:
            self.ledger.settle(r, actual.get(r.pool, 0.0))
            log.info(
                "ledger settled",
                extra={
                    "pool": r.pool,
                    "reserved": r.usd,
                    "actual": round(actual.get(r.pool, 0), 6),
                },
            )
        self.held.clear()


def dead_batch(records: list[TrialRecord], pins: list[str]) -> str | None:
    """Why a batch carries no evidence and the run should stop paying, or None if it is fine."""
    for pin in pins:
        mine = [r for r in records if r.pin == pin]
        if mine and all(r.status is TrialStatus.ERROR for r in mine):
            kinds = sorted({r.exception_type or "unknown" for r in mine})
            return f"every trial of {pin!r} ended in an infrastructure error ({', '.join(kinds)})"
        if not mine:
            return f"no trial of {pin!r} produced a result"
    return None
