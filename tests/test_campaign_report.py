"""The published benchmark numbers are rebuilt from committed evidence, and match it exactly."""

from __future__ import annotations

import importlib.util
import sys

from tests.conftest import REPO_ROOT


def test_committed_campaign_report_is_reproducible() -> None:
    path = REPO_ROOT / "benchmarks" / "campaign_report.py"
    spec = importlib.util.spec_from_file_location("campaign_report", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["campaign_report"] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    committed = (REPO_ROOT / "benchmarks" / "results" / "campaign-2026-10.md").read_text()
    assert module.report() == committed, "regenerate with: benchmarks/campaign_report.py report"
