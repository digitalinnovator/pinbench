"""Guard against committing credentials: scan every git-tracked or staged file for key patterns."""

from __future__ import annotations

import re
import subprocess

import pytest

from tests.conftest import REPO_ROOT

_PATTERNS = {
    "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9]{2,}-[A-Za-z0-9_\-]{20,}"),
    "OpenAI key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{32,}"),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
}


def _tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [line for line in out.splitlines() if line]


def test_no_credentials_in_committable_files() -> None:
    leaks = []
    for rel in _tracked_files():
        path = REPO_ROOT / rel
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        leaks += [f"{rel}: {kind}" for kind, pat in _PATTERNS.items() if pat.search(text)]
    assert not leaks, "possible credentials in committable files:\n" + "\n".join(leaks)
