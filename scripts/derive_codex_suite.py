#!/usr/bin/env python3
"""Derive the Codex variant of the benchmark suite: the same tasks, with the Codex CLI in the image.

Harbor installs a harness inside every sandbox unless the right version is already there. For
Codex that is about 200 MB per trial, too slow on a slow link, so the Codex suite bakes the CLI
into the task image at the pinned version (Harbor then skips its install). Everything else in each
task is copied unchanged, so the tasks differ from the benchmark suite's only in the image.

    python scripts/derive_codex_suite.py            # writes examples/benchmark-suite-codex/tasks
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "examples" / "benchmark-suite" / "tasks"
TARGET = REPO / "examples" / "benchmark-suite-codex" / "tasks"
CODEX_VERSION = "0.163.0"
ANCHOR = "RUN pip install --no-cache-dir pytest==8.4.2\n"
CODEX_LAYER = f"""# Codex CLI baked into the image at the pinned version, so Harbor's install step is skipped
# (it checks `codex --version` against the pin). Per-trial installs of ~200 MB would exceed the
# setup timeout on a slow link (spike 0001). ripgrep is what Codex searches with.
RUN apt-get update \\
 && apt-get install -y --no-install-recommends ripgrep \\
 && rm -rf /var/lib/apt/lists/* \\
 && npm install -g @openai/codex@{CODEX_VERSION} \\
 && codex --version
"""


def main() -> None:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    count = 0
    for task in sorted(SOURCE.iterdir()):
        if not (task / "task.toml").is_file():
            continue
        dest = TARGET / task.name
        shutil.copytree(task, dest)
        dockerfile = dest / "environment" / "Dockerfile"
        text = dockerfile.read_text()
        if ANCHOR not in text:
            raise SystemExit(f"{task.name}: Dockerfile has no '{ANCHOR.strip()}' line to extend")
        dockerfile.write_text(text.replace(ANCHOR, ANCHOR + CODEX_LAYER))
        count += 1
    print(f"wrote {count} tasks to {TARGET.relative_to(REPO)}")


if __name__ == "__main__":
    main()
