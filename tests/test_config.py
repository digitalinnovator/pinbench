from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pinbench.config import PinSpec, load_config
from pinbench.suite import SuiteError, load_suite
from tests.conftest import REPO_ROOT, write_task


def test_real_harness_requires_exact_version() -> None:
    with pytest.raises(ValidationError, match="must set an exact `version`"):
        PinSpec(harness="claude-code")
    assert PinSpec(harness="oracle").version is None


def test_secret_like_env_rejected() -> None:
    with pytest.raises(ValidationError, match="look like secrets"):
        PinSpec(harness="nop", env={"ANTHROPIC_API_KEY": "sk-..."})


def test_version_must_not_hide_in_options() -> None:
    with pytest.raises(ValidationError, match="not in options"):
        PinSpec(harness="codex", version="1", options={"version": "2"})


def test_agent_kwargs_carry_version() -> None:
    pin = PinSpec(harness="claude-code", version="2.1.283", options={"reasoning_effort": "low"})
    assert pin.agent_kwargs() == {"reasoning_effort": "low", "version": "2.1.283"}


def test_fingerprint_tracks_every_pinned_dimension(tmp_path: Path) -> None:
    base = PinSpec(harness="claude-code", version="2.1.283", model="m")
    variants = [
        base.model_copy(update={"version": "2.1.284"}),
        base.model_copy(update={"model": "m2"}),
        base.model_copy(update={"options": {"reasoning_effort": "low"}}),
        base.model_copy(update={"env": {"DISABLE_PROMPT_CACHING": "1"}}),
    ]
    prints = {p.fingerprint(tmp_path) for p in [base, *variants]}
    assert len(prints) == 5


def test_fingerprint_hashes_config_file_content(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("Be terse.\n")
    pin = PinSpec(harness="claude-code", version="1", config_files=[Path("CLAUDE.md")])
    before = pin.fingerprint(tmp_path)
    (tmp_path / "CLAUDE.md").write_text("Be thorough.\n")
    assert pin.fingerprint(tmp_path) != before


def test_invalid_pin_name(tmp_path: Path) -> None:
    (tmp_path / "pinbench.toml").write_text(
        '[suite]\nname = "s"\n[pins."bad name"]\nharness = "nop"\n'
    )
    with pytest.raises(ValidationError, match="invalid pin names"):
        load_config(tmp_path)


def test_unknown_keys_are_errors(tmp_path: Path) -> None:
    (tmp_path / "pinbench.toml").write_text(
        '[suite]\nname = "s"\n[pins.a]\nharness = "nop"\nversoin = "1"\n'
    )
    with pytest.raises(ValidationError, match="versoin"):
        load_config(tmp_path)


@pytest.mark.parametrize("example", ["demo-suite", "simulated"])
def test_shipped_examples_validate(example: str) -> None:
    loaded = load_config(REPO_ROOT / "examples" / example)
    suite = load_suite(loaded)
    assert suite.task_names == ["fix-pagination", "parse-duration", "slugify"]


def test_suite_include_and_digest(tmp_path: Path) -> None:
    for name in ["a", "b"]:
        write_task(tmp_path / "tasks", name)
    (tmp_path / "pinbench.toml").write_text(
        '[suite]\nname = "s"\ninclude = ["b"]\n[pins.x]\nharness = "nop"\n'
    )
    suite = load_suite(load_config(tmp_path))
    assert suite.task_names == ["b"]
    digest = suite.tasks[0].digest
    (tmp_path / "tasks" / "b" / "instruction.md").write_text("changed\n")
    assert load_suite(load_config(tmp_path)).tasks[0].digest != digest


def test_suite_missing_include(tmp_path: Path) -> None:
    write_task(tmp_path / "tasks", "a")
    (tmp_path / "pinbench.toml").write_text(
        '[suite]\nname = "s"\ninclude = ["zzz"]\n[pins.x]\nharness = "nop"\n'
    )
    with pytest.raises(SuiteError, match="zzz"):
        load_suite(load_config(tmp_path))


def test_benchmark_tasks_share_one_image_and_one_verifier_script() -> None:
    """Identical Dockerfiles mean Docker builds the heavy layers once for the whole suite."""
    from tests.conftest import REPO_ROOT

    reference = REPO_ROOT / "examples" / "demo-suite" / "tasks" / "parse-duration"
    tasks = sorted((REPO_ROOT / "examples" / "benchmark-suite" / "tasks").glob("*/task.toml"))
    assert tasks, "the benchmark suite has no tasks"
    for task_toml in tasks:
        task = task_toml.parent
        for rel in ("environment/Dockerfile", "tests/test.sh"):
            assert (task / rel).read_bytes() == (reference / rel).read_bytes(), f"{task.name}/{rel}"
