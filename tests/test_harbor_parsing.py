"""Contract tests against output captured from a real Harbor 0.23.0 run (ADR-0002).

`fixtures/harbor/oracle-job` is the oracle agent on Harbor's hello-world task, captured on
2026-09-27 with absolute paths replaced. If Harbor changes its result schema, these tests fail
before a canary run silently misreads trials.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_canary.config import PinSpec, RunnerConfig
from agent_canary.models import TrialStatus
from agent_canary.runners import BatchRequest, RunnerError
from agent_canary.runners.harbor import (
    HarborTrialResult,
    collect_trials,
    job_config,
    parse_trial,
    pin_identities,
)
from agent_canary.suite import TaskRef
from tests.conftest import FIXTURES

ORACLE_JOB = FIXTURES / "harbor" / "oracle-job"
ORACLE_RESULT = ORACLE_JOB / "hello-world__9H9CnxN" / "result.json"


def _load(path: Path = ORACLE_RESULT) -> HarborTrialResult:
    return HarborTrialResult.model_validate_json(path.read_text())


def test_real_oracle_trial_parses() -> None:
    record = parse_trial(_load(), pin="oracle", batch=0, pass_threshold=1.0, trial_dir="x")
    assert record.task == "hello-world"
    assert record.status is TrialStatus.PASS
    assert record.reward == 1.0
    assert record.installed_version == "1.0.0"
    assert record.reported_cost_usd is None
    assert record.agent_seconds == pytest.approx(0.66855, abs=1e-3)
    assert record.exception_type is None


def _claude_like(tmp_path: Path, **overrides: object) -> Path:
    """The real fixture, edited to look like a Claude Code trial (synthetic until spike 0001)."""
    data = json.loads(ORACLE_RESULT.read_text())
    data["agent_info"] = {"name": "claude-code", "version": "2.1.283", "model_info": None}
    data["config"]["agent"].update(
        {
            "name": "claude-code",
            "model_name": "anthropic/claude-opus-5",
            "kwargs": {"version": "2.1.283", "reasoning_effort": "low"},
        }
    )
    data["agent_result"] = {
        "n_input_tokens": 412_345,
        "n_cache_tokens": 380_000,
        "n_output_tokens": 9_876,
        "cost_usd": 0.4321,
        "model_usage": None,
        "rollout_details": None,
        "metadata": None,
    }
    data.update(overrides)
    path = tmp_path / "trial" / "result.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data))
    return path


def test_tokens_cost_and_version_are_read(tmp_path: Path) -> None:
    record = parse_trial(
        _load(_claude_like(tmp_path)), pin="p", batch=3, pass_threshold=1.0, trial_dir=None
    )
    assert (record.n_input_tokens, record.n_cache_tokens, record.n_output_tokens) == (
        412_345,
        380_000,
        9_876,
    )
    assert record.reported_cost_usd == pytest.approx(0.4321)
    assert record.installed_version == "2.1.283"
    assert record.batch == 3


def test_missing_verifier_result_is_an_error_not_a_failure(tmp_path: Path) -> None:
    path = _claude_like(
        tmp_path,
        verifier_result=None,
        exception_info={
            "exception_type": "EnvironmentStartTimeoutError",
            "exception_message": "docker did not start",
            "exception_traceback": "",
            "occurred_at": "2026-09-26T21:44:22Z",
        },
    )
    record = parse_trial(_load(path), pin="p", batch=0, pass_threshold=1.0, trial_dir=None)
    assert record.status is TrialStatus.ERROR
    assert record.exception_type == "EnvironmentStartTimeoutError"


def test_fractional_reward_uses_threshold(tmp_path: Path) -> None:
    path = _claude_like(tmp_path, verifier_result={"rewards": {"reward": 0.5}})
    assert (
        parse_trial(_load(path), pin="p", batch=0, pass_threshold=1.0, trial_dir=None).status
        is TrialStatus.FAIL
    )
    assert (
        parse_trial(_load(path), pin="p", batch=0, pass_threshold=0.5, trial_dir=None).status
        is TrialStatus.PASS
    )


def test_collect_maps_trials_to_pins(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    job = bundle / "harbor" / "batch-000"
    shutil.copytree(ORACLE_JOB, job)
    records = collect_trials(
        job,
        bundle,
        pin_identities({"oracle": PinSpec(harness="oracle"), "nop": PinSpec(harness="nop")}),
        batch=0,
        pass_threshold=1.0,
    )
    assert [(r.pin, r.task, r.trial_dir) for r in records] == [
        ("oracle", "hello-world", "harbor/batch-000/hello-world__9H9CnxN")
    ]


def test_unmatched_trial_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(RunnerError, match="matches no pin"):
        collect_trials(
            ORACLE_JOB,
            ORACLE_JOB.parent,
            pin_identities({"nop": PinSpec(harness="nop")}),
            batch=0,
            pass_threshold=1.0,
        )


def test_env_distinguishes_pins_but_config_files_cannot() -> None:
    base = PinSpec(harness="claude-code", version="1")
    pin_identities(
        {"a": base, "b": base.model_copy(update={"env": {"DISABLE_PROMPT_CACHING": "1"}})}
    )
    with pytest.raises(RunnerError, match="differ only in config files"):
        pin_identities(
            {"a": base, "b": base.model_copy(update={"config_files": [Path("CLAUDE.md")]})}
        )


def test_job_config_holds_every_arm_in_one_job(tmp_path: Path) -> None:
    pins = {
        "base": PinSpec(
            harness="claude-code",
            version="2.1.283",
            model="anthropic/claude-opus-5",
            options={"reasoning_effort": "high"},
        ),
        "cand": PinSpec(
            harness="claude-code",
            version="2.1.283",
            model="anthropic/claude-opus-5",
            env={"DISABLE_PROMPT_CACHING": "1"},
        ),
    }
    tasks = (TaskRef("a", tmp_path / "a", "d1"), TaskRef("b", tmp_path / "b", "d2"))
    cfg = job_config(
        BatchRequest(2, tasks, pins, 3, tmp_path), RunnerConfig(n_concurrent=8), "batch-002"
    )
    assert cfg["n_attempts"] == 3
    assert cfg["environment"] == {"type": "docker", "delete": False}
    assert cfg["n_concurrent_trials"] == 8
    assert cfg["jobs_dir"] == str(tmp_path / "harbor")
    assert [t["path"] for t in cfg["tasks"]] == [str(tmp_path / "a"), str(tmp_path / "b")]
    assert cfg["agents"] == [
        {
            "name": "claude-code",
            "kwargs": {"reasoning_effort": "high", "version": "2.1.283"},
            "model_name": "anthropic/claude-opus-5",
        },
        {
            "name": "claude-code",
            "kwargs": {"version": "2.1.283"},
            "model_name": "anthropic/claude-opus-5",
            "env": {"DISABLE_PROMPT_CACHING": "1"},
        },
    ]
