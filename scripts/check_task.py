#!/usr/bin/env python3
"""Check a benchmark task offline: no Docker, no harness, no API calls.

A task in Harbor's format is only useful to the canary if its hidden tests fail on the starting
code, pass on the reference solution, and (for tasks with a documented trap) fail on a plausible
careless solution that still passes the visible test. This script checks exactly that by running
the task's own files in a temporary copy of `environment/app`.

    python scripts/check_task.py examples/benchmark-suite/tasks/human-bytes
    python scripts/check_task.py examples/benchmark-suite/tasks/*        # several
    python scripts/check_task.py --json <task>                           # machine-readable

Exit code 0 means every task passed every required check.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REFERENCE_TASK = REPO / "examples" / "demo-suite" / "tasks" / "parse-duration"
MAX_INSTRUCTION_LINES = 40
MAX_STARTING_LINES = 200
MIN_HIDDEN_TESTS, MAX_HIDDEN_TESTS = 10, 40
TIMEOUT = 120


def _pytest(app: Path, *targets: Path | str) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *map(str, targets)]
    try:
        out = subprocess.run(cmd, cwd=app, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, "timed out"
    tail = "\n".join((out.stdout + out.stderr).strip().splitlines()[-6:])
    return out.returncode == 0, tail


def _collected(app: Path, test_file: Path) -> int:
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
    out = subprocess.run(
        [*cmd, str(test_file)], cwd=app, capture_output=True, text=True, timeout=TIMEOUT
    )
    match = re.search(r"(\d+) tests? collected", out.stdout)
    return int(match.group(1)) if match else 0


def _apply(script: Path, app: Path) -> tuple[bool, str]:
    """Run a solve script with /app pointed at the temporary copy."""
    text = script.read_text().replace("/app", str(app))
    out = subprocess.run(
        ["bash", "-c", text], cwd=app, capture_output=True, text=True, timeout=TIMEOUT
    )
    return out.returncode == 0, (out.stdout + out.stderr).strip()[-400:]


def _fresh_app(task: Path, root: Path, name: str) -> Path:
    app = root / name
    shutil.copytree(task / "environment" / "app", app)
    return app


def check_task(task: Path, naive: Path | None) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def record(name: str, ok: bool, detail: str = "", *, required: bool = True) -> None:
        checks.append({"check": name, "ok": ok, "required": required, "detail": detail})

    required_files = [
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "solution/solve.sh",
        "tests/test.sh",
        "tests/test_solution.py",
    ]
    missing = [f for f in required_files if not (task / f).is_file()]
    record("files present", not missing, ", ".join(missing))
    if missing or not (task / "environment" / "app").is_dir():
        return {"task": task.name, "ok": False, "checks": checks}

    config = tomllib.loads((task / "task.toml").read_text())
    name = config.get("task", {}).get("name")
    record("task name", name == f"agent-canary/{task.name}", f"found {name!r}")

    for rel in ("environment/Dockerfile", "tests/test.sh"):
        same = (task / rel).read_bytes() == (REFERENCE_TASK / rel).read_bytes()
        record(f"{rel} identical to the demo task's", same)

    instruction_lines = len((task / "instruction.md").read_text().splitlines())
    record(
        f"instruction at most {MAX_INSTRUCTION_LINES} lines",
        instruction_lines <= MAX_INSTRUCTION_LINES,
        f"{instruction_lines} lines",
    )
    starting = sum(
        len(p.read_text().splitlines())
        for p in (task / "environment" / "app").rglob("*")
        if p.is_file()
    )
    record(
        f"starting files at most {MAX_STARTING_LINES} lines",
        starting <= MAX_STARTING_LINES,
        f"{starting} lines",
    )
    visible = sorted((task / "environment" / "app").rglob("test_*.py"))
    record("has a visible test", bool(visible))

    hidden = task / "tests" / "test_solution.py"
    with tempfile.TemporaryDirectory(prefix="canary-task-") as tmp:
        root = Path(tmp)

        start = _fresh_app(task, root, "start")
        ok, tail = _pytest(start, hidden)
        record("hidden tests fail on the starting code", not ok, tail if ok else "")

        ref = _fresh_app(task, root, "reference")
        applied, detail = _apply(task / "solution" / "solve.sh", ref)
        record("reference solution applies", applied, detail if not applied else "")
        count = _collected(ref, hidden)
        record(
            f"{MIN_HIDDEN_TESTS}-{MAX_HIDDEN_TESTS} hidden test cases",
            MIN_HIDDEN_TESTS <= count <= MAX_HIDDEN_TESTS,
            f"{count} collected",
        )
        ok, tail = _pytest(ref, hidden)
        record("hidden tests pass on the reference solution", ok, "" if ok else tail)
        ok, tail = _pytest(ref, *[v.relative_to(task / "environment" / "app") for v in visible])
        record("visible tests pass on the reference solution", ok, "" if ok else tail)

        if naive is not None and naive.is_file():
            careless = _fresh_app(task, root, "naive")
            applied, detail = _apply(naive, careless)
            record("naive solution applies", applied, detail if not applied else "")
            ok, tail = _pytest(
                careless, *[v.relative_to(task / "environment" / "app") for v in visible]
            )
            record("visible tests pass on the naive solution", ok, "" if ok else tail)
            ok, tail = _pytest(careless, hidden)
            record("hidden tests fail on the naive solution", not ok, tail if ok else "")
        else:
            record("naive solution provided", False, "no naive script", required=False)

    passed = all(c["ok"] for c in checks if c["required"])
    return {"task": task.name, "ok": passed, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tasks", nargs="+", type=Path)
    parser.add_argument("--naive-dir", type=Path, help="Default: <suite>/naive/<task>.sh")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = []
    for task in args.tasks:
        task = task.resolve()
        if not (task / "task.toml").exists():
            continue
        naive_dir = args.naive_dir or task.parent.parent / "naive"
        results.append(check_task(task, naive_dir / f"{task.name}.sh"))

    if args.json:
        print(json.dumps(results, indent=1))
    else:
        for result in results:
            print(f"{'PASS' if result['ok'] else 'FAIL'}  {result['task']}")
            for c in result["checks"]:  # type: ignore[union-attr]
                if not c["ok"]:
                    kind = "required" if c["required"] else "optional"
                    print(f"      {kind}: {c['check']}  {c['detail']}".rstrip())
    return 0 if results and all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
