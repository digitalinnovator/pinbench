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


class ClaimCheck(_Record):
    """Verifier-lite result for one transcript (ADR-0007): a "tests pass" claim against evidence."""

    rules_version: int
    verdict: Literal["no_claim", "supported", "false_success", "unverifiable"]
    reason: (
        Literal["no_test_run_after_last_edit", "test_run_failed", "test_outcome_unknown"] | None
    ) = None
    claim_step: int | None = Field(default=None, description="ATIF step_id of the claim.")
    claim_excerpt: str | None = None
    last_edit_step: int | None = Field(
        default=None, description="ATIF step_id of the last edit before the claim."
    )
    evidence_step: int | None = Field(
        default=None, description="ATIF step_id of the test run the claim was checked against."
    )
    evidence_command: str | None = None
    n_test_runs: int = 0
    edits_after_claim: bool = False


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
    n_cache_write_tokens: int | None = Field(
        default=None, description="Tokens written to the prompt cache (from the transcript)."
    )
    reported_cost_usd: float | None = Field(
        default=None, description="Cost as the harness reported it (see ADR-0005)."
    )
    cost_usd: float | None = Field(
        default=None,
        description="Cost re-priced from token usage with the canary's price table (ADR-0005). "
        "None if the transcript has no usage or uses a model or mode the table does not cover.",
    )
    agent_seconds: float | None = None
    installed_version: str | None = None
    version_source: Literal["trajectory", "runner"] | None = Field(
        default=None,
        description="'trajectory': read from the harness's own transcript (proof of what ran). "
        "'runner': reported by the runner, which may just echo the requested version.",
    )
    harness_stop: str | None = Field(
        default=None,
        description="How the harness ended the trial, e.g. success, error_max_budget_usd, "
        "error_max_turns. A cap that stops one arm more often is itself a treatment.",
    )
    exception_type: str | None = None
    exception_message: str | None = None
    started_at: datetime | None = None
    trial_dir: str | None = Field(default=None, description="Path relative to the bundle root.")
    claim_check: ClaimCheck | None = Field(
        default=None, description="None when the harness wrote no transcript."
    )


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
    checked: int = Field(default=0, description="Trials with a transcript the verifier read.")
    claims: int = Field(default=0, description="Trials whose agent claimed its tests pass.")
    false_success: int = Field(default=0, description="Claims contradicted by the transcript.")
    cap_hits: int = Field(
        default=0, description="Trials the harness stopped at a spend or turn cap."
    )

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
    stop_reason: Literal[
        "significant", "budget_usd", "max_batches", "futility", "dead_batch", "ledger"
    ]
    alternative: Literal["less", "greater", "two-sided"]
    alpha: float
    e_value: float
    p_value: float = Field(description="Anytime-valid p-value: 1 / running max of E.")
    batches_run: int
    spent_usd: float
    cost_known: bool = Field(description="False if any trial had neither cost estimate.")
    n_pairs: int
    n_discordant: int
    n_regress: int
    n_improve: int
    dropped_pairs: int
    baseline: ArmSummary
    candidate: ArmSummary
    metrics: list[RatioEstimate]
    metrics_from_batch: int = Field(
        default=0, description="First batch included in `metrics` ([stats] warmup_batches)."
    )
    per_task: list[TaskSummary]
    history: list[BatchPoint]
