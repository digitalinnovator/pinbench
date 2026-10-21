"""Harbor back-end: generate a JobConfig, run the Harbor CLI, parse its trial directories.

The contract with Harbor is its CLI and on-disk output, not its Python API (ADR-0002). The models
below read only the fields pinbench needs and ignore the rest, so Harbor can add fields freely;
tests/test_harbor_parsing.py pins them against output captured from a real Harbor 0.23.0 run.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from pinbench.config import PinSpec, RunnerConfig
from pinbench.digest import canonical_json
from pinbench.harness_cache import (
    CLAUDE_MOUNT_TARGET,
    CachedBinary,
    HarnessCacheError,
    default_cache_root,
    ensure_claude_code,
    sandbox_platform,
)
from pinbench.models import TrialRecord, TrialStatus
from pinbench.pricing import price_trajectory
from pinbench.runners import BatchRequest, RunnerError, RunnerNotStarted
from pinbench.verifier import check_trajectory

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
# Not a Harbor exception: set by pinbench when the harness says the account is empty.
CREDIT_EXHAUSTED = "CreditExhaustedError"
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
        """The task's directory name, which is how pinbench names tasks."""
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
    if pin.timeout_sec is not None:
        cfg["override_timeout_sec"] = pin.timeout_sec
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
                "does not echo per trial; run them in separate pinbench runs"
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
        # A retried trial is a second bill. Harbor's default is 0; pin it so an upgrade that
        # changes the default cannot double spend (checked again in the job lock).
        "retry": {"max_retries": 0},
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


def load_trajectory(trial_dir: Path) -> dict[str, Any] | None:
    """The trial's ATIF transcript (agent/trajectory.json), if the harness wrote a usable one."""
    try:
        data = json.loads((trial_dir / "agent" / "trajectory.json").read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def trajectory_version(trajectory: dict[str, Any]) -> str | None:
    """The harness version recorded in the ATIF transcript, which is what actually ran.

    Harbor's `agent_info.version` echoes the requested version when one is pinned, even if setup
    failed before anything was installed (spike 0001), so it cannot prove a pin held.
    """
    version = (trajectory.get("agent") or {}).get("version")
    return version if isinstance(version, str) and version not in ("", "unknown") else None


# The whole message, not a mention of it: a task about billing must not look like an empty account.
_CREDIT_EXHAUSTED = re.compile(
    r"\s*(?:api error:?[^\n]{0,40}?)?credit balance is too low\W*", re.IGNORECASE
)


def harness_result(trial_dir: Path) -> dict[str, Any] | None:
    """Claude Code's final `result` event from its stream-json log, if there is one."""
    path = trial_dir / "agent" / "claude-code.txt"
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        if '"type":"result"' not in line and '"type": "result"' not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            return event
    return None


def out_of_credit(trial_dir: Path, result: dict[str, Any] | None) -> bool:
    """True if the harness reported that the API account has run dry.

    Harbor has no pattern for this message, so without this check the trial would score as an
    agent failure and an empty account would look like a regression. Only the harness's own
    error result counts, or an agent turn that is nothing but the message: the task instruction
    and ordinary agent prose that mentions the phrase do not.
    """
    if result is not None:
        return result.get("is_error") is True and bool(
            _CREDIT_EXHAUSTED.fullmatch(str(result.get("result") or ""))
        )
    trajectory = load_trajectory(trial_dir) or {}
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or step.get("source") != "agent" or step.get("tool_calls"):
            continue
        message = step.get("message")
        if isinstance(message, str) and _CREDIT_EXHAUSTED.fullmatch(message):
            return True
    return False


def from_transcript(trajectory: dict[str, Any]) -> dict[str, Any]:
    """TrialRecord fields that only the transcript can supply: proof of version, claims, cost."""
    update: dict[str, Any] = {}
    ran = trajectory_version(trajectory)
    if ran is not None:
        update |= {"installed_version": ran, "version_source": "trajectory"}
    if trajectory.get("steps"):
        update["claim_check"] = check_trajectory(trajectory)
    priced = price_trajectory(trajectory)
    if priced is not None:
        update |= {"cost_usd": priced.cost_usd, "n_cache_write_tokens": priced.cache_write_tokens}
    return update


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
        trajectory = load_trajectory(result_path.parent)
        if trajectory is not None:
            record = record.model_copy(update=from_transcript(trajectory))
        final = harness_result(result_path.parent)
        if final is not None and isinstance(final.get("subtype"), str):
            record = record.model_copy(update={"harness_stop": final["subtype"]})
            # The harness stopped itself at its spend or turn cap. Its non-zero exit is then
            # explained, so the trial is scored by the hidden tests like any other, even if
            # Harbor's text patterns took something in its output for an infrastructure error.
            if final["subtype"].startswith("error_max_") and record.reward is not None:
                scored = TrialStatus.PASS if record.reward >= pass_threshold else TrialStatus.FAIL
                record = record.model_copy(update={"status": scored})
        if record.status is not TrialStatus.PASS and out_of_credit(result_path.parent, final):
            record = record.model_copy(
                update={"status": TrialStatus.ERROR, "exception_type": CREDIT_EXHAUSTED}
            )
        records.append(record)
    return records


# ------------------------------------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------------------------------------


class HarborRunner:
    # Real harness trials call paid APIs, so the orchestrator must reserve them in the ledger.
    spends_money = True

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

    def _jobs(self, pins: dict[str, PinSpec]) -> list[tuple[str, dict[str, PinSpec]]]:
        """Split a batch's pins into Harbor jobs: (job-name suffix, pins).

        Harbor mounts are job-wide, and the cached harness binary is a mount (ADR-0006). So pins
        on different Claude Code versions get one job per version, run concurrently, each with
        its own binary mounted. Everything else stays in a single job.
        """
        versions = sorted(
            {p.version for p in pins.values() if p.harness == "claude-code" and p.version}
        )
        if not self._config.harness_cache or len(versions) < 2:
            return [("", pins)]
        jobs = [
            (
                f"-cc{version}",
                {
                    name: pin
                    for name, pin in pins.items()
                    if pin.harness == "claude-code" and pin.version == version
                },
            )
            for version in versions
        ]
        jobs[0][1].update({n: p for n, p in pins.items() if p.harness != "claude-code"})
        return jobs

    def _cached_harnesses(self, pins: dict[str, PinSpec]) -> list[CachedBinary]:
        """The verified host copy of the one Claude Code version a job's pins use, if any."""
        if not self._config.harness_cache:
            return []
        versions = {p.version for p in pins.values() if p.harness == "claude-code" and p.version}
        if len(versions) != 1:
            return []
        root = self._config.harness_cache_dir or default_cache_root()
        return [ensure_claude_code(versions.pop(), root, sandbox_platform())]

    def _env_file(self) -> Path | None:
        if self._config.env_file is None:
            return None
        env_file = self._config.env_file
        return env_file if env_file.is_absolute() else self._cwd / env_file

    def validate(self, pins: dict[str, PinSpec]) -> None:
        """Reject a run that could never start. Free: no download, no Docker, no API call."""
        pin_identities(pins)
        env_file = self._env_file()
        if env_file is not None and not env_file.is_file():
            raise RunnerError(f"env_file {env_file} does not exist")
        self.version()

    def run_batch(self, request: BatchRequest) -> list[TrialRecord]:
        # Everything up to the first job launch is free. A failure here is reported as "not
        # started" so the caller can release the batch's ledger reservation.
        try:
            self.validate(request.pins)
            identities = pin_identities(request.pins)
            jobs = self._jobs(request.pins)
            prepared = [
                (f"batch-{request.batch:03d}{suffix}", pins, self._cached_harnesses(pins))
                for suffix, pins in jobs
            ]
        except (RunnerError, HarnessCacheError, OSError) as exc:
            raise RunnerNotStarted(str(exc)) from exc
        # Several jobs share the concurrency budget, so API load matches the single-job case.
        concurrency = max(1, self._config.n_concurrent // len(jobs))
        started = time.monotonic()
        log.info(
            "starting harbor batch",
            extra={
                "batch": request.batch,
                "tasks": len(request.tasks),
                "pins": list(request.pins),
                "jobs": len(jobs),
            },
        )
        with ThreadPoolExecutor(max_workers=len(prepared)) as pool:
            futures = [
                pool.submit(
                    self._run_job, request, job_name, pins, binaries, identities, concurrency
                )
                for job_name, pins, binaries in prepared
            ]
            records = [r for f in futures for r in f.result()]
        expected = len(request.tasks) * len(request.pins) * request.attempts
        log.info(
            "harbor batch finished",
            extra={
                "batch": request.batch,
                "trials": len(records),
                "expected": expected,
                "seconds": round(time.monotonic() - started, 1),
            },
        )
        if len(records) != expected:
            log.warning(
                "batch produced an unexpected number of trials", extra={"batch": request.batch}
            )
        return records

    def _run_job(
        self,
        request: BatchRequest,
        job_name: str,
        pins: dict[str, PinSpec],
        binaries: list[CachedBinary],
        identities: dict[str, str],
        concurrency: int,
    ) -> list[TrialRecord]:
        configs_dir = request.bundle_dir / "harbor-configs"
        configs_dir.mkdir(parents=True, exist_ok=True)
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
                job_config(
                    replace(request, pins=pins),
                    self._config.model_copy(update={"n_concurrent": concurrency}),
                    job_name,
                    harness_mounts(binaries),
                ),
                sort_keys=False,
            )
        )
        log_path = configs_dir / f"{job_name}.log"
        args = ["run", "-c", str(config_path), "-y", "-q"]
        env_file = self._env_file()
        if env_file is not None:
            args += ["--env-file", str(env_file)]
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
                raise RunnerError(f"harbor job {job_name} timed out; see {log_path}") from exc
        job_dir = request.bundle_dir / "harbor" / job_name
        if proc.returncode != 0 and not job_dir.is_dir():
            raise RunnerError(f"harbor exited {proc.returncode} with no job output; see {log_path}")
        self._check_job_lock(job_dir)
        log.info("harbor job finished", extra={"job": job_name, "exit_code": proc.returncode})
        return collect_trials(
            job_dir,
            request.bundle_dir,
            identities,
            batch=request.batch,
            pass_threshold=self._pass_threshold,
        )

    def _check_job_lock(self, job_dir: Path) -> None:
        lock_path = job_dir / "lock.json"
        if not lock_path.exists():
            return
        lock = json.loads(lock_path.read_text())
        locked = lock.get("harbor", {}).get("version")
        if locked and locked != self.version():
            raise RunnerError(f"job ran on Harbor {locked}, expected {self.version()}")
        retries = (lock.get("retry") or {}).get("max_retries")
        if retries not in (None, 0):
            raise RunnerError(f"job ran with {retries} retries allowed; retried trials bill twice")
