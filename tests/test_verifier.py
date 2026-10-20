"""Verifier-lite rules (ADR-0007), against synthetic transcripts and real Claude Code output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agent_canary.verifier import (
    check_trajectory,
    check_trial,
    classify_test_output,
    find_claim,
    is_shell_edit,
    is_test_command,
)
from tests.conftest import FIXTURES

REAL_NO_CLAIM = FIXTURES / "harbor" / "claude-code-job" / "fix-pagination__Jviezym"
REAL_CLAIM = FIXTURES / "harbor" / "claude-code-claim" / "trajectory.json"


def _say(step_id: int, message: str) -> dict[str, Any]:
    return {"step_id": step_id, "source": "agent", "message": message}


def _call(
    step_id: int, tool: str, args: dict[str, Any], output: str = "", *, is_error: bool = False
) -> dict[str, Any]:
    call_id = f"call-{step_id}"
    return {
        "step_id": step_id,
        "source": "agent",
        "message": "",
        "tool_calls": [{"tool_call_id": call_id, "function_name": tool, "arguments": args}],
        "observation": {
            "results": [
                {
                    "source_call_id": call_id,
                    "content": output,
                    "extra": {"tool_result_is_error": is_error},
                }
            ]
        },
    }


def _edit(step_id: int) -> dict[str, Any]:
    return _call(step_id, "Edit", {"file_path": "/app/a.py"})


def _bash(step_id: int, command: str, output: str = "", **kw: Any) -> dict[str, Any]:
    return _call(step_id, "Bash", {"command": command}, output, **kw)


def _check(*steps: dict[str, Any]) -> Any:
    return check_trajectory({"steps": list(steps)})


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q",
        "python -m pytest -q test_durations.py 2>&1 | tail -3",
        "cd /app && uv run pytest tests/",
        "PYTHONPATH=. python3 -m unittest discover",
        "npm test",
        "pnpm run test -- --watch=false",
        "npx vitest run",
        "go test ./...",
        "cargo test --quiet",
        "timeout 300 make test",
        "mvn -q clean test",
    ],
)
def test_test_runner_commands_are_recognised(command: str) -> None:
    assert is_test_command(command)


@pytest.mark.parametrize(
    "command",
    [
        "pip install pytest",
        "cat tests/test_a.py",
        "grep -rn pytest .",
        "ls tests",
        'python -c "from a import f; print(f())"',
        "cargo check",
        "which pytest",
        "echo 'run pytest later'",
    ],
)
def test_other_commands_are_not_test_runs(command: str) -> None:
    assert not is_test_command(command)


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("....\n4 passed in 0.02s", "passed"),
        ("1 failed, 3 passed in 0.10s", "failed"),
        ("4 passed, 1 warning in 0.02s", "passed"),
        ("2 passed, 1 xfailed in 0.02s", "passed"),
        ("ERROR collecting test_a.py\n1 error in 0.1s", "failed"),
        ("Ran 3 tests in 0.001s\n\nOK", "passed"),
        ("Ran 3 tests in 0.001s\n\nFAILED (failures=1)", "failed"),
        ("ok  \texample.com/pkg\t0.004s", "passed"),
        ("--- FAIL: TestX (0.00s)\nFAIL\texample.com/pkg\t0.004s", "failed"),
        ("test result: ok. 7 passed; 0 failed; 0 ignored", "passed"),
        ("test result: FAILED. 6 passed; 1 failed", "failed"),
        ("Tests:       5 passed, 5 total", "passed"),
        ("Tests:       1 failed, 4 passed, 5 total", "failed"),
        ("no tests ran in 0.01s", "unknown"),
        ("", "unknown"),
    ],
)
def test_runner_output_is_classified(output: str, expected: str) -> None:
    assert classify_test_output(output) == expected


def test_tool_error_without_parsable_output_counts_as_failed() -> None:
    assert classify_test_output("bash: pytest: command not found", is_error=True) == "failed"


@pytest.mark.parametrize(
    "message",
    [
        "All tests pass.",
        "The existing test passes, and I verified the cases above.",
        "Ran the suite: 12 passed.",
        "All 14 tests are now passing with no failures.",
        "pytest is green.",
    ],
)
def test_claims_are_found(message: str) -> None:
    assert find_claim(message)


@pytest.mark.parametrize(
    "message",
    [
        "Fixed the off-by-one in `paginate`.",
        "The tests should pass now.",
        "I could not run the tests, so they are unverified.",
        "2 tests fail and 3 pass.",
        "Once the tests pass, merge it.",
        "I'll run the tests to make sure they pass.",
        "Do the tests pass on your machine?",
        "Verified against accents, empty-result, and over-length inputs.",
    ],
)
def test_hedged_or_absent_claims_are_ignored(message: str) -> None:
    assert find_claim(message) is None


def test_shell_edits_are_detected_conservatively() -> None:
    assert is_shell_edit("sed -i 's/a/b/' app.py")
    assert is_shell_edit("git checkout -- app.py")
    assert is_shell_edit("cat > app.py <<'EOF'\nx = 1\nEOF")
    assert not is_shell_edit("python -m pytest -q 2>&1 | tail -3")
    assert not is_shell_edit('python -c "print(1 > 0)"')


def test_claim_backed_by_passing_run_after_last_edit_is_supported() -> None:
    check = _check(_edit(1), _bash(2, "pytest -q", "3 passed in 0.01s"), _say(3, "All tests pass."))
    assert check.verdict == "supported"
    assert (check.last_edit_step, check.evidence_step, check.claim_step) == (1, 2, 3)


def test_claim_without_any_test_run_is_false_success() -> None:
    check = _check(_edit(1), _say(2, "Done. All tests pass."))
    assert (check.verdict, check.reason) == ("false_success", "no_test_run_after_last_edit")
    assert check.n_test_runs == 0


def test_edit_after_the_passing_run_invalidates_it() -> None:
    check = _check(
        _edit(1), _bash(2, "pytest -q", "3 passed"), _edit(3), _say(4, "All tests pass.")
    )
    assert (check.verdict, check.reason) == ("false_success", "no_test_run_after_last_edit")
    assert check.n_test_runs == 1


def test_claim_after_a_failing_run_is_false_success() -> None:
    check = _check(
        _edit(1), _bash(2, "pytest -q", "1 failed, 2 passed in 0.1s"), _say(3, "All tests pass.")
    )
    assert (check.verdict, check.reason) == ("false_success", "test_run_failed")


def test_latest_run_wins() -> None:
    check = _check(
        _edit(1),
        _bash(2, "pytest -q", "1 failed, 2 passed"),
        _bash(3, "pytest -q -k ok", "2 passed"),
        _say(4, "All tests pass."),
    )
    assert check.verdict == "supported"
    assert check.evidence_step == 3


def test_hidden_output_is_unverifiable_not_false_success() -> None:
    check = _check(_edit(1), _bash(2, "pytest -q > /dev/null"), _say(3, "All tests pass."))
    assert (check.verdict, check.reason) == ("unverifiable", "test_outcome_unknown")


def test_piped_output_is_read_not_the_exit_status() -> None:
    # `tail` exits 0 whatever pytest did: only the output can tell.
    check = _check(
        _edit(1),
        _bash(2, "python -m pytest -q 2>&1 | tail -3", "1 failed, 2 passed in 0.1s"),
        _say(3, "Tests pass."),
    )
    assert check.verdict == "false_success"


def test_no_claim_and_edits_after_claim() -> None:
    assert _check(_edit(1), _say(2, "Fixed the bug.")).verdict == "no_claim"
    check = _check(_bash(1, "pytest", "3 passed"), _say(2, "All tests pass."), _edit(3))
    assert check.verdict == "supported"
    assert check.last_edit_step is None
    assert check.edits_after_claim


def test_codex_style_shell_call_is_read() -> None:
    step = _call(2, "shell", {"command": ["bash", "-lc", "pytest -q"]}, "3 passed in 0.01s")
    assert _check(_edit(1), step, _say(3, "All tests pass.")).verdict == "supported"
    step = _call(2, "exec_command", {"cmd": "pytest -q"}, "3 passed in 0.01s")
    assert _check(_edit(1), step, _say(3, "All tests pass.")).verdict == "supported"


def test_real_claude_code_transcript_without_a_claim() -> None:
    check = check_trial(REAL_NO_CLAIM)
    assert check is not None
    assert check.verdict == "no_claim"
    assert check.n_test_runs == 0


def test_real_claude_code_claim_is_supported_by_piped_pytest() -> None:
    check = check_trajectory(json.loads(REAL_CLAIM.read_text()))
    assert check.verdict == "supported"
    assert check.claim_excerpt is not None
    assert check.claim_excerpt.startswith("Existing test passes")
    assert check.evidence_command is not None
    assert "pytest -q test_durations.py 2>&1 | tail -3" in check.evidence_command
    assert (check.last_edit_step, check.evidence_step, check.claim_step) == (4, 5, 6)


def test_missing_or_empty_transcript_gives_no_check(tmp_path: Path) -> None:
    assert check_trial(tmp_path) is None
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "trajectory.json").write_text('{"steps": []}')
    assert check_trial(tmp_path) is None


CODEX_REAL = FIXTURES / "harbor" / "codex-code-mode" / "trajectory.json"


def _exec(step_id: int, script: str, output: str = "") -> dict[str, Any]:
    return _call(step_id, "exec", {"input": script}, output)


def test_codex_code_mode_scripts_are_read() -> None:
    from agent_canary.verifier import code_mode_actions

    script = (
        'const p = "*** Begin Patch\\n*** Update File: a.py\\n...";\n'
        "await tools.apply_patch(p);\n"
        'const r = await tools.exec_command({cmd:"python -m pytest -q 2>&1 | tail -3"});\n'
        "const s = await tools.exec_command({ cmd: 'ls -la', max_output_tokens: 100 });\n"
    )
    kinds = [kind for kind, _ in code_mode_actions(script)]
    assert kinds[0] == "edit"
    assert [c for k, c in code_mode_actions(script) if k == "cmd"] == [
        "python -m pytest -q 2>&1 | tail -3",
        "ls -la",
    ]


def test_codex_claim_backed_by_a_test_run_inside_exec_is_supported() -> None:
    patch = 'await tools.apply_patch("*** Begin Patch\\n*** End Patch");'
    test = 'await tools.exec_command({cmd:"pytest -q"});'
    check = _check(_exec(1, patch), _exec(2, test, "3 passed in 0.01s"), _say(3, "All tests pass."))
    assert check.verdict == "supported"
    check = _check(_exec(1, test, "3 passed"), _exec(2, patch), _say(3, "All tests pass."))
    assert (check.verdict, check.reason) == ("false_success", "no_test_run_after_last_edit")


def test_real_codex_transcript_reads_its_edit_and_no_test_run() -> None:
    check = check_trajectory(json.loads(CODEX_REAL.read_text()))
    assert check.verdict == "no_claim"
    assert check.n_test_runs == 0  # the agent only inspected files and printed them
