"""Task-suite discovery. A suite is a directory of Harbor-format tasks (ADR-0002)."""

from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from agent_canary.config import LoadedConfig
from agent_canary.digest import sha256_tree

TASK_MARKER = "task.toml"


@dataclass(frozen=True)
class TaskRef:
    name: str
    path: Path
    digest: str


@dataclass(frozen=True)
class GitInfo:
    commit: str
    dirty: bool


@dataclass(frozen=True)
class Suite:
    name: str
    root: Path
    tasks: tuple[TaskRef, ...]
    git: GitInfo | None

    @property
    def task_names(self) -> list[str]:
        return [t.name for t in self.tasks]


class SuiteError(ValueError):
    pass


def load_suite(loaded: LoadedConfig) -> Suite:
    cfg = loaded.config.suite
    tasks_dir = (
        cfg.tasks_dir if cfg.tasks_dir.is_absolute() else loaded.root / cfg.tasks_dir
    ).resolve()
    if not tasks_dir.is_dir():
        raise SuiteError(f"tasks_dir {tasks_dir} does not exist")
    found = {p.parent.name: p.parent for p in sorted(tasks_dir.glob(f"*/{TASK_MARKER}"))}
    if cfg.include is not None:
        missing = sorted(set(cfg.include) - set(found))
        if missing:
            raise SuiteError(f"included tasks not found in {tasks_dir}: {missing}")
        found = {name: found[name] for name in cfg.include}
    if not found:
        raise SuiteError(f"no Harbor tasks (*/{TASK_MARKER}) under {tasks_dir}")
    for name, path in found.items():
        _refuse_multi_step(name, path / TASK_MARKER)
    tasks = tuple(
        TaskRef(name=name, path=path, digest=sha256_tree(path))
        for name, path in sorted(found.items())
    )
    return Suite(name=cfg.name, root=tasks_dir, tasks=tasks, git=_git_info(tasks_dir))


def _refuse_multi_step(name: str, task_toml: Path) -> None:
    """A multi-step Harbor task runs the harness once per step, each with a fresh spend cap and
    timeout, so one per-trial cap does not bound it and its cost is not read correctly either."""
    try:
        config = tomllib.loads(task_toml.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SuiteError(f"task {name!r}: cannot read {TASK_MARKER}: {exc}") from None
    if config.get("steps"):
        raise SuiteError(
            f"task {name!r} is a multi-step Harbor task ([[steps]]). Each step runs the harness "
            "again with its own spend cap, which the canary's per-trial budget does not cover. "
            "Multi-step tasks are not supported"
        )


def _git_info(path: Path) -> GitInfo | None:
    try:
        commit = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain", "--", "."],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return GitInfo(commit=commit, dirty=bool(status.strip()))
