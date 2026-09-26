"""A seeded, in-process runner for tests, demos and power analysis. It spends nothing.

Each task gets a latent difficulty on the logit scale, shared by all pins, so simulated outcomes
have the task heterogeneity that makes pairing matter. Metrics are drawn from log-normal
distributions around each arm's configured means.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from agent_canary.config import SimulatedArm
from agent_canary.digest import sha256_text
from agent_canary.models import TrialRecord, TrialStatus
from agent_canary.runners import BatchRequest, RunnerError


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class SimulatedRunner:
    def __init__(
        self,
        arms: dict[str, SimulatedArm],
        *,
        seed: int,
        task_spread: float = 1.5,
        metric_sigma: float = 0.25,
    ) -> None:
        self._arms = arms
        self._seed = seed
        self._spread = task_spread
        self._sigma = metric_sigma

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "simulated",
            "seed": self._seed,
            "task_spread": self._spread,
            "arms": {name: arm.model_dump() for name, arm in self._arms.items()},
        }

    def _difficulty(self, task: str) -> float:
        # Stable per task and seed, independent of batch order.
        rng = np.random.default_rng([self._seed, int(sha256_text(task)[:12], 16)])
        return float(rng.normal(0.0, self._spread))

    def pass_probability(self, pin: str, task: str) -> float:
        return _sigmoid(_logit(self._arms[pin].pass_rate) + self._difficulty(task))

    def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
        missing = sorted(set(request.pins) - set(self._arms))
        if missing:
            raise RunnerError(f"simulated runner has no [runner.simulated] entry for {missing}")
        rng = np.random.default_rng([self._seed, request.batch])
        records: list[TrialRecord] = []
        for task in request.tasks:
            for pin_name in request.pins:
                arm = self._arms[pin_name]
                p = self.pass_probability(pin_name, task.name)
                for attempt in range(request.attempts):
                    passed = bool(rng.random() < p)
                    noise = rng.lognormal(-0.5 * self._sigma**2, self._sigma, size=4)
                    records.append(
                        TrialRecord(
                            trial_name=f"{task.name}__{pin_name}__b{request.batch}a{attempt}",
                            task=task.name,
                            pin=pin_name,
                            batch=request.batch,
                            status=TrialStatus.PASS if passed else TrialStatus.FAIL,
                            reward=1.0 if passed else 0.0,
                            n_input_tokens=int(arm.input_tokens * noise[0]),
                            n_cache_tokens=0,
                            n_output_tokens=int(arm.output_tokens * noise[1]),
                            reported_cost_usd=round(arm.cost_usd * float(noise[2]), 6),
                            agent_seconds=round(arm.agent_seconds * float(noise[3]), 3),
                            installed_version=request.pins[pin_name].version,
                            version_source="trajectory",
                        )
                    )
        return records
