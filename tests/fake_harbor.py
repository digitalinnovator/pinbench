"""A stand-in for the Harbor CLI: reads a JobConfig and writes one passing trial per agent x task.

Used as `[runner] harbor_command` to test HarborRunner's process handling without Docker.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def main(argv: list[str]) -> int:
    if argv == ["--version"]:
        print("0.23.0")
        return 0
    config = yaml.safe_load(Path(argv[argv.index("-c") + 1]).read_text())
    job_dir = Path(config["jobs_dir"]) / config["job_name"]
    for task in config["tasks"]:
        name = Path(task["path"]).name
        for i, agent in enumerate(config["agents"]):
            trial = job_dir / f"{name}__{config['job_name']}-{i}"
            trial.mkdir(parents=True)
            version = agent.get("kwargs", {}).get("version")
            result = {
                "task_name": name,
                "trial_name": trial.name,
                "task_id": {"path": task["path"]},
                "config": {"agent": agent},
                "agent_info": {"name": agent["name"], "version": version},
                "agent_result": {"n_input_tokens": 10, "n_output_tokens": 1, "cost_usd": 0.01},
                "verifier_result": {"rewards": {"reward": 1.0}},
            }
            (trial / "result.json").write_text(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
