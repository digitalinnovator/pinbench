"""Cost re-pricing from token usage (ADR-0005)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from pinbench.budget import BatchPlan, trial_cost
from pinbench.models import TrialStatus
from pinbench.pricing import (
    load_price_table,
    normalise_model,
    price_trajectory,
    usage_from_trajectory,
)
from pinbench.stats import cost_metric
from tests.conftest import FIXTURES, record

REAL = FIXTURES / "harbor" / "claude-code-job" / "fix-pagination__Jviezym" / "agent"


def _step(model: str = "claude-opus-5", **metrics: Any) -> dict[str, Any]:
    extra = metrics.pop("extra", {})
    return {"source": "agent", "model_name": model, "metrics": {**metrics, "extra": extra}}


def _price(*steps: dict[str, Any]) -> float | None:
    priced = price_trajectory({"steps": list(steps)})
    return priced.cost_usd if priced else None


def test_table_is_internally_consistent() -> None:
    table = load_price_table()
    assert table.version == table.verified.isoformat()
    assert len(table.sha256) == 64
    assert set(table.sources) == {"anthropic", "openai"}
    read_multiplier = {
        "claude-fable-5-1": 0.025,
        "claude-opus-5-5": 0.05,
        "claude-sonnet-5-5": 0.05,
    }
    claude = {name: price for name, price in table.models.items() if name.startswith("claude-")}
    assert len(claude) == 13
    for name, price in claude.items():
        # The published multipliers; a typo in one cell breaks one of these.
        assert price.cache_write_5m == pytest.approx(1.25 * price.input), name
        assert price.cache_write_1h == pytest.approx(2 * price.input), name
        assert price.cache_read == pytest.approx(read_multiplier.get(name, 0.1) * price.input), name
        assert price.output == pytest.approx(5 * price.input), name
    for name, price in table.models.items():
        if name.startswith("gpt-"):
            assert price.cache_write_5m == price.cache_write_1h == pytest.approx(1.25 * price.input)
            assert price.cache_read < price.input < price.output, name
            assert price.long_context_tokens == 272_000


def test_codex_usage_is_priced_with_its_own_cache_write_field() -> None:
    # The shape Harbor's Codex adapter writes: cached tokens and cache writes inside prompt_tokens.
    step = _step(
        "openai/gpt-6-luna",
        prompt_tokens=270_000,
        cached_tokens=90_000,
        completion_tokens=90_000,
        extra={"cache_write_input_tokens": 90_000, "reasoning_output_tokens": 5},
    )
    # 90k uncached at $0.10, 90k cache writes at $0.125, 90k cache reads at $0.01, 90k out at $0.50
    assert _price(step) == pytest.approx(0.09 * (0.10 + 0.125 + 0.01 + 0.50))


def test_tiers_and_long_context_the_table_does_not_hold_are_left_unpriced() -> None:
    ok = _step("gpt-6-luna", prompt_tokens=272_000, completion_tokens=10)
    assert _price(ok) is not None
    assert _price(_step("gpt-6-luna", prompt_tokens=272_001, completion_tokens=10)) is None
    priority = _step("gpt-6-luna", prompt_tokens=1000, extra={"service_tier": "priority"})
    assert _price(priority) is None
    assert _price(_step("gpt-6-luna", prompt_tokens=1000, extra={"service_tier": "default"}))


@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-5",
        "anthropic/claude-opus-5",
        "Anthropic/Claude-Opus-5",
        "claude-opus-5-20260401",
    ],
)
def test_model_ids_are_normalised(model: str) -> None:
    assert normalise_model(model) == "claude-opus-5"
    assert load_price_table().price_for(model) is not None


def test_real_trial_reprices_to_what_the_harness_reported() -> None:
    trajectory = json.loads((REAL / "trajectory.json").read_text())
    (usage,) = (usage_from_trajectory(trajectory) or {}).values()
    assert (usage.uncached_input, usage.cache_write_5m, usage.cache_read, usage.output) == (
        8,
        6681,
        58_605,
        709,
    )
    priced = price_trajectory(trajectory)
    assert priced is not None
    assert priced.cost_usd == pytest.approx(trajectory["final_metrics"]["total_cost_usd"])
    assert priced.cache_write_tokens == 6681


def test_each_token_category_has_its_own_price() -> None:
    # 1M of each on Opus 5: uncached $5, 5m write $6.25, 1h write $10, read $0.50, output $25.
    step = _step(
        prompt_tokens=4_000_000,
        cached_tokens=1_000_000,
        completion_tokens=1_000_000,
        extra={
            "cache_creation_input_tokens": 2_000_000,
            "cache_creation": {
                "ephemeral_5m_input_tokens": 1_000_000,
                "ephemeral_1h_input_tokens": 1_000_000,
            },
        },
    )
    assert _price(step) == pytest.approx(5 + 6.25 + 10 + 0.5 + 25)


def test_models_are_priced_separately_and_modifiers_apply() -> None:
    opus = _step(prompt_tokens=1_000_000, completion_tokens=0)
    haiku = _step("claude-haiku-4-5", prompt_tokens=1_000_000, completion_tokens=0)
    assert _price(opus, haiku) == pytest.approx(5 + 1)
    us = _step(prompt_tokens=1_000_000, completion_tokens=0, extra={"inference_geo": "us"})
    assert _price(us) == pytest.approx(5.5)
    search = _step(prompt_tokens=0, extra={"server_tool_use": {"web_search_requests": 3}})
    assert _price(search) == pytest.approx(0.03)


def test_uncovered_usage_is_left_unpriced_not_mispriced() -> None:
    ok = _step(prompt_tokens=1000, completion_tokens=10)
    assert _price(ok) is not None
    assert _price(ok, _step("gpt-5.5-codex", prompt_tokens=1000)) is None
    assert _price(ok, _step(prompt_tokens=1000, extra={"speed": "fast"})) is None
    assert _price({"source": "user", "message": "hi"}) is None
    assert price_trajectory({}) is None


def test_cost_metric_needs_every_trial_repriced() -> None:
    priced = record(pin="a").model_copy(update={"cost_usd": 0.1})
    assert cost_metric([priced, priced]) == ("cost_usd", "cost_usd")
    assert cost_metric([priced, record(pin="b")]) == ("reported_cost_usd", "reported_cost_usd")
    # A trial that errored before the agent ran never has a cost and does not force the fallback.
    errored = record(pin="b", status=TrialStatus.ERROR, cost=None)
    assert cost_metric([priced, errored]) == ("cost_usd", "cost_usd")


def test_budget_counts_the_higher_estimate_and_fails_closed() -> None:
    low_table = record(cost=0.30).model_copy(update={"cost_usd": 0.10})
    low_report = record(cost=0.10).model_copy(update={"cost_usd": 0.25})
    assert trial_cost(low_table) == 0.30
    assert trial_cost(low_report) == 0.25
    plan = BatchPlan(trials_per_pin=2, caps={"a": 0.40}, pools={"a": "anthropic"}, paid=True)
    assert plan.spent([low_table, low_report]) == (pytest.approx(0.55), True)
    # A trial with no cost is charged at its cap, never at zero.
    assert plan.spent([low_table, record(cost=None)]) == (pytest.approx(0.70), False)
