"""`pinbench.toml`: suite metadata, pins, statistics settings and budgets."""

from __future__ import annotations

import math
import re
import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pinbench.digest import canonical_json, sha256_file, sha256_text

CONFIG_FILENAME = "pinbench.toml"

# Harbor agents that install nothing, so a version pin is meaningless for them.
UNVERSIONED_HARNESSES = frozenset({"oracle", "nop"})

# Harnesses whose CLI enforces a per-trial dollar cap that Harbor can pass (max_budget_usd).
DOLLAR_CAP_HARNESSES = frozenset({"claude-code"})

# The pool for a pin whose model has no "provider/" prefix.
_HARNESS_POOL = {"claude-code": "anthropic", "codex": "openai"}

_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)
_PIN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PinSpec(_Strict):
    """One cell of the version matrix: harness x version x model x config."""

    harness: str = Field(description="Harbor agent name, e.g. claude-code, codex, opencode.")
    version: str | None = Field(default=None, description="Exact harness CLI version.")
    model: str | None = Field(default=None, description="Model id as Harbor expects it.")
    options: dict[str, Any] = Field(
        default_factory=dict, description="Harbor agent kwargs, e.g. reasoning_effort."
    )
    env: dict[str, str] = Field(
        default_factory=dict, description="Non-secret environment overrides for the agent."
    )
    config_files: list[Path] = Field(
        default_factory=list,
        description="Files whose content is part of the pin (CLAUDE.md, MCP config, ...).",
    )
    timeout_sec: Annotated[float, Field(gt=0)] | None = Field(
        default=None,
        description="Agent timeout for every trial of this pin, overriding each task's own. "
        "The only bound on a trial for harnesses with no dollar cap (Codex, OpenCode).",
    )
    reserve_usd: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = Field(
        default=None,
        description="Worst-case dollars one trial of this pin can cost, for the campaign ledger. "
        "Required, with timeout_sec, for a paid harness that has no dollar cap. For Claude Code "
        "it can only raise the reservation above max_budget_usd plus the in-flight allowance, "
        "never lower it. Not part of the fingerprint.",
    )

    @field_validator("env")
    @classmethod
    def _no_secrets(cls, env: dict[str, str]) -> dict[str, str]:
        leaked = sorted(k for k in env if _SECRET_NAME.search(k))
        if leaked:
            raise ValueError(
                f"env keys {leaked} look like secrets; set them in the process environment "
                "instead of pinbench.toml (pins are fingerprinted and stored in run bundles)"
            )
        return env

    @field_validator("options")
    @classmethod
    def _version_not_in_options(cls, options: dict[str, Any]) -> dict[str, Any]:
        if "version" in options:
            raise ValueError("set the harness version with `version = ...`, not in options")
        return options

    @model_validator(mode="after")
    def _budget_cap_shape(self) -> PinSpec:
        if "max_budget_usd" not in self.options:
            return self
        if self.harness not in DOLLAR_CAP_HARNESSES:
            raise ValueError(
                f"max_budget_usd is a Claude Code flag; harness {self.harness!r} has no dollar "
                "cap. Bound its trials with timeout_sec and reserve_usd instead"
            )
        value = self.options["max_budget_usd"]
        if not isinstance(value, str) or self.harness_cap_usd() is None:
            raise ValueError(
                'options.max_budget_usd must be a string holding a positive number, e.g. "0.20" '
                "(Harbor passes it to --max-budget-usd as text)"
            )
        return self

    @model_validator(mode="after")
    def _require_version(self) -> PinSpec:
        if self.harness not in UNVERSIONED_HARNESSES and not self.version:
            raise ValueError(
                f"pin for harness {self.harness!r} must set an exact `version`; "
                "unpinned harnesses make comparisons meaningless"
            )
        return self

    def pool(self) -> str | None:
        """The credit pool a trial of this pin draws on; None if it costs nothing."""
        if self.harness in UNVERSIONED_HARNESSES:
            return None
        if self.model and "/" in self.model:
            return self.model.split("/", 1)[0].lower()
        return _HARNESS_POOL.get(self.harness, self.harness)

    def harness_cap_usd(self) -> float | None:
        """The dollar cap the harness itself enforces on a trial, if it has one."""
        if self.harness not in DOLLAR_CAP_HARNESSES:
            return None
        try:
            cap = float(self.options["max_budget_usd"])
        except (KeyError, TypeError, ValueError):
            return None
        return cap if math.isfinite(cap) and cap > 0 else None

    def trial_cap_usd(self, inflight_allowance_usd: float) -> float | None:
        """Worst-case cost of one trial for the ledger, or None if nothing enforces a bound.

        A number here must be backed by something that stops the trial: Claude Code's own
        `--max-budget-usd`, or an agent timeout for harnesses with no dollar cap. `reserve_usd`
        alone stops nothing, so it never counts as a bound by itself and can never lower one.

        Claude Code checks its cap between messages, so a trial can overshoot by the request in
        flight. The allowance is an estimate of that request, not a bound on it.
        """
        if self.pool() is None:
            return 0.0
        enforced = self.harness_cap_usd()
        if enforced is not None:
            return max(enforced + inflight_allowance_usd, self.reserve_usd or 0.0)
        if self.harness in DOLLAR_CAP_HARNESSES:
            return None  # the harness has a cap flag and the pin does not set it
        if self.reserve_usd is not None and self.timeout_sec is not None:
            return self.reserve_usd
        return None

    def agent_kwargs(self) -> dict[str, Any]:
        kwargs = dict(self.options)
        if self.version:
            kwargs["version"] = self.version
        return kwargs

    def fingerprint(self, base_dir: Path) -> str:
        """SHA-256 of the canonical spec plus the content of referenced config files."""
        files = {
            p.as_posix(): sha256_file(p if p.is_absolute() else base_dir / p)
            for p in sorted(self.config_files)
        }
        spec: dict[str, Any] = {
            "harness": self.harness,
            "version": self.version,
            "model": self.model,
            "options": self.options,
            "env": self.env,
            "config_files": files,
        }
        if self.timeout_sec is not None:  # added only when set, so older fingerprints stay valid
            spec["timeout_sec"] = self.timeout_sec
        return sha256_text(canonical_json(spec))


class SuiteConfig(_Strict):
    name: str
    tasks_dir: Path = Path("tasks")
    include: list[str] | None = Field(
        default=None, description="Task directory names to run; default all."
    )


class StatsConfig(_Strict):
    alpha: Annotated[float, Field(gt=0, lt=1)] = 0.05
    alternative: Literal["less", "greater", "two-sided"] = Field(
        default="less",
        description="'less': alarm when the candidate is worse (regression).",
    )
    mixture_max: Annotated[float, Field(gt=0.5, le=1.0)] = Field(
        default=0.8,  # chosen by benchmarks/power_simulation.py; see ADR-0003
        description=(
            "Upper end of the e-process's uniform mixture over q = P(regress | discordant). "
            "Lower values favour small regressions; any value keeps the false-alarm guarantee."
        ),
    )
    pass_threshold: float = Field(default=1.0, description="reward >= threshold counts as pass.")
    bootstrap_resamples: Annotated[int, Field(ge=100)] = 2000
    confidence: Annotated[float, Field(gt=0, lt=1)] = 0.95
    cost_threshold: Annotated[float, Field(ge=0)] = Field(
        default=0.10, description="Flag cost/latency increases above this relative change."
    )
    warmup_batches: Annotated[int, Field(ge=0)] = Field(
        default=0,
        description=(
            "Leave the first N batches out of the cost, token and latency comparison. They still "
            "count for pass rate and budget. The first trials of a configuration pay a prompt-"
            "cache write that later ones do not (spike 0001), which matters on small suites."
        ),
    )
    futility_after_batches: Annotated[int, Field(ge=1)] | None = Field(
        default=None,
        description=(
            "Look once, after this many batches, and stop unless the candidate is behind by at "
            "least `futility_min_net_regressions`. Stopping early for futility cannot raise the "
            "false-alarm rate, because the e-process is valid at every batch boundary."
        ),
    )
    futility_min_net_regressions: Annotated[int, Field(ge=1)] = Field(
        default=4, description="Regressed pairs minus improved pairs needed to continue."
    )
    seed: int = 20260927

    @model_validator(mode="after")
    def _futility_is_one_sided(self) -> StatsConfig:
        if self.futility_after_batches is not None and self.alternative != "less":
            raise ValueError('futility_after_batches needs alternative = "less"')
        return self


class BudgetConfig(_Strict):
    max_usd: Annotated[float, Field(ge=0, allow_inf_nan=False)] = Field(
        default=10.0,
        description="Soft stop for one compare run: no new batch once spend plus the average "
        "batch cost would pass it. The hard bound is the campaign ledger (ADR-0009).",
    )
    max_batches: Annotated[int, Field(ge=1)] = 10
    attempts_per_batch: Annotated[int, Field(ge=1)] = Field(
        default=1, description="Attempts per task per arm in each batch (k)."
    )
    inflight_allowance_usd: Annotated[float, Field(ge=0, allow_inf_nan=False)] = Field(
        default=0.05,
        description="Floor for the amount added to max_budget_usd when reserving a trial. "
        "Claude Code checks its dollar cap between messages, so one request can run past it; "
        "pinbench uses the larger of this and one typical request at the model's prices.",
    )


class SimulatedArm(_Strict):
    pass_rate: Annotated[float, Field(gt=0, lt=1)]
    cost_usd: Annotated[float, Field(ge=0)] = 0.25
    input_tokens: Annotated[int, Field(ge=0)] = 120_000
    output_tokens: Annotated[int, Field(ge=0)] = 6_000
    agent_seconds: Annotated[float, Field(ge=0)] = 90.0


class RunnerConfig(_Strict):
    kind: Literal["harbor", "simulated"] = "harbor"
    harbor_command: list[str] = Field(
        default_factory=lambda: ["harbor"],
        description="Command prefix for the Harbor CLI; runs with cwd = the pinbench.toml dir.",
    )
    env_file: Path | None = Field(
        default=None,
        description="Gitignored .env with API keys, passed to `harbor run --env-file`.",
    )
    environment: str = "docker"
    keep_images: bool = Field(
        default=False,
        description=(
            "Keep built task images between trials. Harbor tags one image per trial, so this "
            "accumulates images; with a warm Docker build cache the rebuild saving is small."
        ),
    )
    harness_cache: bool = Field(
        default=True,
        description=(
            "Download each pinned harness binary once on the host, verify it against the "
            "vendor manifest, and mount it read-only into sandboxes (Claude Code, glibc images)."
        ),
    )
    harness_cache_dir: Path | None = Field(
        default=None, description="Default: $XDG_CACHE_HOME/pinbench/harness."
    )
    n_concurrent: Annotated[int, Field(ge=1)] = 4
    agent_setup_timeout_multiplier: Annotated[float, Field(gt=0)] | None = Field(
        default=None,
        description="Scales Harbor's agent-setup timeout (360 s by default), which covers "
        "installing the harness inside each sandbox.",
    )
    batch_timeout_sec: Annotated[float, Field(gt=0)] = 4 * 3600
    simulated: dict[str, SimulatedArm] = Field(
        default_factory=dict, description="Per-pin behaviour for the simulated runner."
    )
    simulated_task_spread: Annotated[float, Field(ge=0)] = Field(
        default=1.5, description="Std-dev of per-task difficulty on the logit scale."
    )


class AlertsConfig(_Strict):
    """Where to send alerts. Secrets are named here and read from the environment."""

    on: list[Literal["regression", "cost_increase", "false_success"]] = Field(
        default=["regression"],
        description="Conditions that send an alert. cost_increase: the cost or latency ratio is "
        "flagged by its interval. false_success: more contradicted claims than the baseline.",
    )
    slack_webhook_env: str | None = Field(
        default=None, description="Name of the env var holding a Slack incoming-webhook URL."
    )
    github_repo: str | None = Field(default=None, description="owner/name to open issues in.")
    github_token_env: str = "GITHUB_TOKEN"
    github_labels: list[str] = Field(default_factory=lambda: ["pinbench"], min_length=1)
    github_api_url: str = "https://api.github.com"

    @field_validator("slack_webhook_env", "github_token_env")
    @classmethod
    def _env_name_not_value(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError("must be the NAME of an environment variable, not the secret itself")
        return value

    @field_validator("github_repo")
    @classmethod
    def _repo_shape(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[\w.-]+/[\w.-]+", value):
            raise ValueError("github_repo must look like owner/name")
        return value


class WatchConfig(_Strict):
    """Test each new release of a harness against a baseline pin (`pinbench watch`)."""

    baseline: str = Field(description="Pin to compare new releases against.")
    channel: str = Field(default="latest", description="npm dist-tag to follow, e.g. stable.")


class StorageConfig(_Strict):
    home: Path = Path(".pinbench")


class PinbenchConfig(_Strict):
    suite: SuiteConfig
    pins: dict[str, PinSpec]
    stats: StatsConfig = StatsConfig()
    budget: BudgetConfig = BudgetConfig()
    runner: RunnerConfig = RunnerConfig()
    storage: StorageConfig = StorageConfig()
    alerts: AlertsConfig = AlertsConfig()
    watch: dict[str, WatchConfig] = Field(default_factory=dict)

    @field_validator("pins")
    @classmethod
    def _pin_names(cls, pins: dict[str, PinSpec]) -> dict[str, PinSpec]:
        bad = [n for n in pins if not _PIN_NAME.match(n)]
        if bad:
            raise ValueError(f"invalid pin names {bad}: use letters, digits, '.', '_' or '-'")
        return pins

    @model_validator(mode="after")
    def _watches_name_pins(self) -> PinbenchConfig:
        for name, watch in self.watch.items():
            if watch.baseline not in self.pins:
                raise ValueError(f"watch {name!r}: unknown baseline pin {watch.baseline!r}")
        return self


class LoadedConfig(BaseModel):
    """A validated config plus the directory it was loaded from (relative paths resolve here)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    config: PinbenchConfig
    path: Path

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def home(self) -> Path:
        home = self.config.storage.home
        return home if home.is_absolute() else self.root / home

    def pin(self, name: str) -> PinSpec:
        try:
            return self.config.pins[name]
        except KeyError:
            known = ", ".join(sorted(self.config.pins)) or "(none)"
            raise KeyError(f"unknown pin {name!r}; defined pins: {known}") from None

    def with_pin(self, name: str, pin: PinSpec) -> LoadedConfig:
        """A copy with one extra pin that is not in pinbench.toml (a release under test)."""
        config = self.config.model_copy(update={"pins": {**self.config.pins, name: pin}})
        return self.model_copy(update={"config": config})


def load_config(path: Path) -> LoadedConfig:
    path = path.resolve()
    if path.is_dir():
        path = path / CONFIG_FILENAME
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return LoadedConfig(config=PinbenchConfig.model_validate(raw), path=path)
