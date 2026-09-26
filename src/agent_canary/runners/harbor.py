"""Harbor back-end: generate a JobConfig, run the Harbor CLI, parse its trial directories.

The contract with Harbor is its CLI and on-disk output, not its Python API (ADR-0002). The models
below read only the fields the canary needs and ignore the rest, so Harbor can add fields freely;
tests/test_harbor_parsing.py pins them against output captured from a real Harbor 0.23.0 run.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from agent_canary.config import PinSpec, RunnerConfig
from agent_canary.digest import canonical_json
from agent_canary.harness_cache import (
    CLAUDE_MOUNT_TARGET,
    CachedBinary,
    default_cache_root,
    ensure_claude_code,
    sandbox_platform,
)
from agent_canary.models import TrialRecord, TrialStatus
from agent_canary.runners import BatchRequest, RunnerError

log = logging.getLogger(__name__)

_MAX_MESSAGE = 2000

# Harbor exceptions that say nothing about the harness under test: the trial becomes ERROR and is
# excluded from pairing even if the verifier still wrote a reward. Everything else, including
# AgentTimeoutError, ContextWindowExceededError, OutputTokenExceededError, AgentSafetyRefusalError
# and a plain harness crash, stays attributable to the harness: a new version causing them is a
# regression. Caveat (ADR-0003): if one arm provokes more rate limiting, excluding those trials
# biases the comparison; the report shows errors per arm.
INFRASTRUCTURE_EXCEPTIONS = frozenset(
    {
        "AgentAuthenticationError",
        "ModelNotFoundError",
        "NetworkConnectionError",
        "ApiConnectionClosedError",
        "ApiInternalServerError",
        "ApiOverloadedError",
        "ApiProviderResourceNotFoundError",
        "ApiRateLimitError",
        "ApiResponseStalledError",
        "ApiUsageLimitError",
        "UnknownApiError",
        "AgentSetupTimeoutError",
        "EnvironmentStartTimeoutError",
        "SandboxBuildFailedError",
        "HealthcheckError",
        "VerifierTimeoutError",
        "VerifierOutputParseError",
        "RewardFileEmptyError",
        "RewardFileNotFoundError",
        "AddTestsDirError",
        "DownloadVerifierDirError",
    }
)
_VERSION_RE = re.compile(r"\d+\.\d+\.\d+\S*")


# ------------------------------------------------------------------------------------------------
# Tolerant views of Harbor's result.json (only what we use)
# ------------------------------------------------------------------------------------------------


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Timing(_Loose):
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None


class _AgentCfg(_Loose):
    name: str | None = None
    model_name: str | None = None
    kwargs: dict[str, Any] = {}
    env: dict[str, str] = {}  # non-secret values are echoed literally by Harbor


class _TrialCfg(_Loose):
    agent: _AgentCfg


class _AgentInfo(_Loose):
    name: str
    version: str | None = None


class _AgentResult(_Loose):
    n_input_tokens: int | None = None
    n_cache_tokens: int | None = None
    n_output_tokens: int | None = None
    cost_usd: float | None = None


class _VerifierResult(_Loose):
    rewards: dict[str, float | int | None] | None = None


class _ExceptionInfo(_Loose):
    exception_type: str
    exception_message: str = ""


class HarborTrialResult(_Loose):
    task_name: str
    trial_name: str
    task_id: dict[str, Any] = {}
    config: _TrialCfg
    agent_info: _AgentInfo
    agent_result: _AgentResult | None = None
    verifier_result: _VerifierResult | None = None
    exception_info: _ExceptionInfo | None = None
    started_at: datetime | None = None
    agent_execution: _Timing | None = None

    @property
    def task_dir_name(self) -> str:
        """The task's directory name, which is how the canary names tasks."""
        path = self.task_id.get("path")
        return Path(path).name if path else self.task_name.rsplit("/", 1)[-1]

    def reward(self) -> float | None:
        rewards = (self.verifier_result.rewards if self.verifier_result else None) or {}
        if "reward" in rewards:
            value = rewards["reward"]
        elif len(rewards) == 1:
            value = next(iter(rewards.values()))
        else:
            return None
        return None if value is None else float(value)


# ------------------------------------------------------------------------------------------------
# JobConfig generation and trial -> pin mapping
# ------------------------------------------------------------------------------------------------


def agent_config(pin: PinSpec) -> dict[str, Any]:
    cfg: dict[str, Any] = {"name": pin.harness, "kwargs": pin.agent_kwargs()}
    if pin.model:
        cfg["model_name"] = pin.model
    if pin.env:
        cfg["env"] = dict(pin.env)
    return cfg


def _identity(
    name: str | None, model: str | None, kwargs: dict[str, Any], env: dict[str, str]
) -> str:
    return canonical_json({"name": name, "model": model, "kwargs": kwargs, "env": env})


def pin_identities(pins: dict[str, PinSpec]) -> dict[str, str]:
    """Map Harbor-visible identity -> pin name, refusing pins Harbor output can't tell apart."""
    seen: dict[str, str] = {}
    for name, pin in pins.items():
        ident = _identity(pin.harness, pin.model, pin.agent_kwargs(), dict(pin.env))
        if ident in seen:
            raise RunnerError(
                f"pins {seen[ident]!r} and {name!r} differ only in config files, which Harbor "
                "does not echo per trial; run them in separate canary runs"
            )
        seen[ident] = name
    return seen


def job_config(
    request: BatchRequest,
    runner: RunnerConfig,
    job_name: str,
    mounts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "job_name": job_name,
        "jobs_dir": str(request.bundle_dir / "harbor"),
        "n_attempts": request.attempts,
        "n_concurrent_trials": runner.n_concurrent,
        "quiet": True,
        # delete=False still removes containers (`compose down`); it only keeps the images.
        "environment": {"type": runner.environment, "delete": not runner.keep_images},
        "agents": [agent_config(pin) for pin in request.pins.values()],
        "tasks": [{"path": str(task.path)} for task in request.tasks],
    }
    if runner.agent_setup_timeout_multiplier is not None:
        cfg["agent_setup_timeout_multiplier"] = runner.agent_setup_timeout_multiplier
    if mounts:
        cfg["environment"]["mounts"] = mounts
    return cfg


def harness_mounts(binaries: list[CachedBinary]) -> list[dict[str, Any]]:
    """Bind-mount cached harness binaries where Harbor's install check will find them."""
    return [
        {"type": "bind", "source": str(b.path), "target": CLAUDE_MOUNT_TARGET, "read_only": True}
        for b in binaries
        if b.harness == "claude-code"
    ]


def parse_trial(
    result: HarborTrialResult,
    *,
    pin: str,
    batch: int,
    pass_threshold: float,
    trial_dir: str | None,
) -> TrialRecord:
    reward = result.reward()
    exc = result.exception_info
    if reward is None or (exc is not None and exc.exception_type in INFRASTRUCTURE_EXCEPTIONS):
        status = TrialStatus.ERROR
    elif reward >= pass_threshold:
        status = TrialStatus.PASS
    else:
        status = TrialStatus.FAIL
    agent = result.agent_result or _AgentResult()
    return TrialRecord(
        trial_name=result.trial_name,
        task=result.task_dir_name,
        pin=pin,
        batch=batch,
        status=status,
        reward=reward,
        n_input_tokens=agent.n_input_tokens,
        n_cache_tokens=agent.n_cache_tokens,
        n_output_tokens=agent.n_output_tokens,
        reported_cost_usd=agent.cost_usd,
        agent_seconds=result.agent_execution.seconds() if result.agent_execution else None,
        installed_version=result.agent_info.version,
        version_source="runner" if result.agent_info.version else None,
        exception_type=exc.exception_type if exc else None,
        exception_message=exc.exception_message[:_MAX_MESSAGE] if exc else None,
        started_at=result.started_at,
        trial_dir=trial_dir,
    )


def trajectory_version(trial_dir: Path) -> str | None:
    """The harness version recorded in the ATIF transcript, which is what actually ran.

    Harbor's `agent_info.version` echoes the requested version when one is pinned, even if setup
    failed before anything was installed (spike 0001), so it cannot prove a pin held.
    """
    path = trial_dir / "agent" / "trajectory.json"
    try:
        agent = json.loads(path.read_text()).get("agent") or {}
    except (OSError, ValueError):
        return None
    version = agent.get("version")
    return version if isinstance(version, str) and version not in ("", "unknown") else None


def collect_trials(
    job_dir: Path,
    bundle_dir: Path,
    identities: dict[str, str],
    *,
    batch: int,
    pass_threshold: float,
) -> list[TrialRecord]:
    records: list[TrialRecord] = []
    for result_path in sorted(job_dir.glob("*/result.json")):
        result = HarborTrialResult.model_validate_json(result_path.read_text())
        agent = result.config.agent
        ident = _identity(agent.name, agent.model_name, agent.kwargs, agent.env)
        pin = identities.get(ident)
        if pin is None:
            raise RunnerError(f"trial {result.trial_name} matches no pin (agent config {ident})")
        record = parse_trial(
            result,
            pin=pin,
            batch=batch,
            pass_threshold=pass_threshold,
            trial_dir=result_path.parent.relative_to(bundle_dir).as_posix(),
        )
        ran = trajectory_version(result_path.parent)
        if ran is not None:
            record = record.model_copy(
                update={"installed_version": ran, "version_source": "trajectory"}
            )
        records.append(record)
    return records


# ------------------------------------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------------------------------------


class HarborRunner:
    def __init__(self, config: RunnerConfig, *, cwd: Path, pass_threshold: float) -> None:
        self._config = config
        self._cwd = cwd
        self._pass_threshold = pass_threshold
        self._version: str | None = None

    def _run(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        cmd = [*self._config.harbor_command, *args]
        try:
            return subprocess.run(cmd, cwd=self._cwd, text=True, env=os.environ.copy(), **kwargs)
        except FileNotFoundError as exc:
            raise RunnerError(
                f"Harbor CLI not found ({cmd[0]!r}); install the pinned tool env with "
                "`uv sync --project tools/harbor --frozen` or set [runner] harbor_command"
            ) from exc

    def version(self) -> str:
        if self._version is None:
            out = self._run(["--version"], capture_output=True, check=False)
            match = _VERSION_RE.search(out.stdout or "")
            if out.returncode != 0 or not match:
                raise RunnerError(f"could not determine Harbor version: {out.stderr.strip()}")
            self._version = match.group(0)
        return self._version

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "harbor",
            "harbor_version": self.version(),
            "harbor_command": self._config.harbor_command,
            "environment": self._config.environment,
            "n_concurrent": self._config.n_concurrent,
        }

    def _cached_harnesses(self, pins: dict[str, PinSpec]) -> list[CachedBinary]:
        """Cache the pinned Claude Code binary when every Claude Code pin shares one version.

        Harbor mounts are job-wide, so pins with different Claude Code versions in one job fall
        back to Harbor's in-sandbox install (slow, but correct).
        """
        if not self._config.harness_cache:
            return []
        versions = {p.version for p in pins.values() if p.harness == "claude-code" and p.version}
        if len(versions) != 1:
            if len(versions) > 1:
                log.warning(
                    "pins use different Claude Code versions; installing inside each sandbox",
                    extra={"versions": sorted(versions)},
                )
            return []
        root = self._config.harness_cache_dir or default_cache_root()
        return [ensure_claude_code(versions.pop(), root, sandbox_platform())]

    def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
        identities = pin_identities(request.pins)
        job_name = f"batch-{request.batch:03d}"
        configs_dir = request.bundle_dir / "harbor-configs"
        configs_dir.mkdir(parents=True, exist_ok=True)
        binaries = self._cached_harnesses(request.pins)
        if binaries:
            (configs_dir / f"{job_name}.harness.json").write_text(
                json.dumps(
                    [
                        {
                            "harness": b.harness,
                            "version": b.version,
                            "platform": b.platform,
                            "sha256": b.sha256,
                            "source_url": b.source_url,
                        }
                        for b in binaries
                    ],
                    indent=2,
                )
                + "\n"
            )
        config_path = configs_dir / f"{job_name}.yaml"
        config_path.write_text(
            yaml.safe_dump(
                job_config(request, self._config, job_name, harness_mounts(binaries)),
                sort_keys=False,
            )
        )
        log_path = configs_dir / f"{job_name}.log"
        log.info(
            "starting harbor batch",
            extra={"batch": request.batch, "tasks": len(request.tasks), "pins": list(request.pins)},
        )
        args = ["run", "-c", str(config_path), "-y", "-q"]
        if self._config.env_file is not None:
            env_file = self._config.env_file
            env_file = env_file if env_file.is_absolute() else self._cwd / env_file
            if not env_file.is_file():
                raise RunnerError(f"env_file {env_file} does not exist")
            args += ["--env-file", str(env_file)]
        started = time.monotonic()
        with log_path.open("w") as log_file:
            try:
                proc = self._run(
                    args,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    timeout=self._config.batch_timeout_sec,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RunnerError(
                    f"harbor batch {request.batch} timed out; see {log_path}"
                ) from exc
        job_dir = request.bundle_dir / "harbor" / job_name
        if proc.returncode != 0 and not job_dir.is_dir():
            raise RunnerError(f"harbor exited {proc.returncode} with no job output; see {log_path}")
        self._check_job_lock(job_dir)
        records = collect_trials(
            job_dir,
            request.bundle_dir,
            identities,
            batch=request.batch,
            pass_threshold=self._pass_threshold,
        )
        expected = len(request.tasks) * len(request.pins) * request.attempts
        log.info(
            "harbor batch finished",
            extra={
                "batch": request.batch,
                "trials": len(records),
                "expected": expected,
                "seconds": round(time.monotonic() - started, 1),
                "exit_code": proc.returncode,
            },
        )
        if len(records) != expected:
            log.warning(
                "batch produced an unexpected number of trials", extra={"batch": request.batch}
            )
        return records

    def _check_job_lock(self, job_dir: Path) -> None:
        lock_path = job_dir / "lock.json"
        if not lock_path.exists():
            return
        locked = json.loads(lock_path.read_text()).get("harbor", {}).get("version")
        if locked and locked != self.version():
            raise RunnerError(f"job ran on Harbor {locked}, expected {self.version()}")
