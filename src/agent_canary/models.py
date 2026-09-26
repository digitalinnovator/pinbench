"""Normalised records written to run bundles. These are the canary's own schema, not Harbor's."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BUNDLE_SCHEMA_VERSION = 1


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TrialStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"  # no verifier reward: infrastructure failure, excluded from statistics


class TrialRecord(_Record):
    trial_name: str
    task: str
    pin: str
    batch: int
    status: TrialStatus
    reward: float | None = None
    n_input_tokens: int | None = None
    n_cache_tokens: int | None = None
    n_output_tokens: int | None = None
    reported_cost_usd: float | None = Field(
        default=None, description="Cost as the harness reported it (see ADR-0005)."
    )
    agent_seconds: float | None = None
    installed_version: str | None = None
    version_source: Literal["trajectory", "runner"] | None = Field(
        default=None,
        description="'trajectory': read from the harness's own transcript (proof of what ran). "
        "'runner': reported by the runner, which may just echo the requested version.",
    )
    exception_type: str | None = None
    exception_message: str | None = None
    started_at: datetime | None = None
    trial_dir: str | None = Field(default=None, description="Path relative to the bundle root.")


class PinRecord(_Record):
    name: str
    fingerprint: str
    spec: dict[str, Any]


class TaskRecord(_Record):
    name: str
    digest: str


class RunManifest(_Record):
    schema_version: int = BUNDLE_SCHEMA_VERSION
    run_id: str
    kind: Literal["run", "compare"]
    created_at: datetime
    canary_version: str
    runner: dict[str, Any]
    suite_name: str
    suite_commit: str | None
    suite_dirty: bool | None
    tasks: list[TaskRecord]
    pins: list[PinRecord]
    baseline: str | None = None
    candidate: str | None = None
    settings: dict[str, Any] = Field(description="Stats, budget and runner settings used.")


class BatchPoint(_Record):
    batch: int
    n_pairs: int
    n_discordant: int
    n_regress: int
    n_improve: int
    e_value: float
    spent_usd: float


class RatioEstimate(_Record):
    metric: str
    baseline_mean: float
    candidate_mean: float
    ratio: float
    ci_low: float
    ci_high: float
    n_baseline: int
    n_candidate: int
    flagged: bool


class ArmSummary(_Record):
    pin: str
    n: int
    passes: int
    errors: int

    @property
    def pass_rate(self) -> float | None:
        return self.passes / self.n if self.n else None


class TaskSummary(_Record):
    task: str
    baseline_passes: int
    baseline_n: int
    candidate_passes: int
    candidate_n: int
    n_regress: int
    n_improve: int


class Verdict(_Record):
    decision: Literal["regression", "improvement", "inconclusive"]
    stop_reason: Literal["significant", "budget_usd", "max_batches"]
    alternative: Literal["less", "greater", "two-sided"]
    alpha: float
    e_value: float
    p_value: float = Field(description="Anytime-valid p-value: 1 / running max of E.")
    batches_run: int
    spent_usd: float
    cost_known: bool = Field(description="False if any trial lacked a reported cost.")
    n_pairs: int
    n_discordant: int
    n_regress: int
    n_improve: int
    dropped_pairs: int
    baseline: ArmSummary
    candidate: ArmSummary
    metrics: list[RatioEstimate]
    per_task: list[TaskSummary]
    history: list[BatchPoint]
