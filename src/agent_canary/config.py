"""`canary.toml`: suite metadata, pins, statistics settings and budgets."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from agent_canary.digest import canonical_json, sha256_file, sha256_text

CONFIG_FILENAME = "canary.toml"

# Harbor agents that install nothing, so a version pin is meaningless for them.
UNVERSIONED_HARNESSES = frozenset({"oracle", "nop"})

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

    @field_validator("env")
    @classmethod
    def _no_secrets(cls, env: dict[str, str]) -> dict[str, str]:
        leaked = sorted(k for k in env if _SECRET_NAME.search(k))
        if leaked:
            raise ValueError(
                f"env keys {leaked} look like secrets; set them in the process environment "
                "instead of canary.toml (pins are fingerprinted and stored in run bundles)"
            )
        return env

    @field_validator("options")
    @classmethod
    def _version_not_in_options(cls, options: dict[str, Any]) -> dict[str, Any]:
        if "version" in options:
            raise ValueError("set the harness version with `version = ...`, not in options")
        return options

    @model_validator(mode="after")
    def _require_version(self) -> PinSpec:
        if self.harness not in UNVERSIONED_HARNESSES and not self.version:
            raise ValueError(
                f"pin for harness {self.harness!r} must set an exact `version`; "
                "unpinned harnesses make comparisons meaningless"
            )
        return self

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
        spec = {
            "harness": self.harness,
            "version": self.version,
            "model": self.model,
            "options": self.options,
            "env": self.env,
            "config_files": files,
        }
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
    pass_threshold: float = Field(default=1.0, description="reward >= threshold counts as pass.")
    bootstrap_resamples: Annotated[int, Field(ge=100)] = 2000
    confidence: Annotated[float, Field(gt=0, lt=1)] = 0.95
    cost_threshold: Annotated[float, Field(ge=0)] = Field(
        default=0.10, description="Flag cost/latency increases above this relative change."
    )
    seed: int = 20260927


class BudgetConfig(_Strict):
    max_usd: Annotated[float, Field(ge=0)] = 10.0
    max_batches: Annotated[int, Field(ge=1)] = 10
    attempts_per_batch: Annotated[int, Field(ge=1)] = Field(
        default=1, description="Attempts per task per arm in each batch (k)."
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
        description="Command prefix for the Harbor CLI; runs with cwd = the canary.toml dir.",
    )
    env_file: Path | None = Field(
        default=None,
        description="Gitignored .env with API keys, passed to `harbor run --env-file`.",
    )
    environment: str = "docker"
    keep_images: bool = Field(
        default=True,
        description=(
            "Keep built task images between trials. Harbor's delete mode runs "
            "`docker compose down --rmi local`, which forces a rebuild in every batch."
        ),
    )
    n_concurrent: Annotated[int, Field(ge=1)] = 4
    batch_timeout_sec: Annotated[float, Field(gt=0)] = 4 * 3600
    simulated: dict[str, SimulatedArm] = Field(
        default_factory=dict, description="Per-pin behaviour for the simulated runner."
    )
    simulated_task_spread: Annotated[float, Field(ge=0)] = Field(
        default=1.5, description="Std-dev of per-task difficulty on the logit scale."
    )


class StorageConfig(_Strict):
    home: Path = Path(".canary")


class CanaryConfig(_Strict):
    suite: SuiteConfig
    pins: dict[str, PinSpec]
    stats: StatsConfig = StatsConfig()
    budget: BudgetConfig = BudgetConfig()
    runner: RunnerConfig = RunnerConfig()
    storage: StorageConfig = StorageConfig()

    @field_validator("pins")
    @classmethod
    def _pin_names(cls, pins: dict[str, PinSpec]) -> dict[str, PinSpec]:
        bad = [n for n in pins if not _PIN_NAME.match(n)]
        if bad:
            raise ValueError(f"invalid pin names {bad}: use letters, digits, '.', '_' or '-'")
        return pins


class LoadedConfig(BaseModel):
    """A validated config plus the directory it was loaded from (relative paths resolve here)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    config: CanaryConfig
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


def load_config(path: Path) -> LoadedConfig:
    path = path.resolve()
    if path.is_dir():
        path = path / CONFIG_FILENAME
    with path.open("rb") as f:
        raw = tomllib.load(f)
    return LoadedConfig(config=CanaryConfig.model_validate(raw), path=path)
