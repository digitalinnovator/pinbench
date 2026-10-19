"""Re-price a trial from its token usage with a price table versioned in this repo (ADR-0005).

Harnesses estimate cost on the client, from a price table bundled into each build or fetched at
runtime, so reported dollars are not comparable across harness versions. Token counts are. This
module reads per-request usage from the ATIF transcript and prices it with `data/prices.toml`.

A trial is priced only if every request in it can be: an unknown model, fast mode or missing
usage leaves the whole trial un-priced (None), never partly priced.
"""

from __future__ import annotations

import re
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from functools import cache
from importlib import resources
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_canary.digest import sha256_text

_PROVIDER_PREFIX = re.compile(r"^[a-z0-9_.-]+/")
_DATE_SUFFIX = re.compile(r"-\d{8}$")
_MTOK = 1_000_000


class ModelPrice(BaseModel):
    """US dollars per million tokens."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input: float = Field(ge=0)
    cache_write_5m: float = Field(ge=0)
    cache_write_1h: float = Field(ge=0)
    cache_read: float = Field(ge=0)
    output: float = Field(ge=0)
    long_context_tokens: int | None = Field(
        default=None,
        description="A request with more input tokens than this is priced higher by the "
        "provider. The table does not hold those rates, so such a trial is left un-priced.",
    )


class Modifiers(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    inference_geo_us_multiplier: float = Field(ge=1)
    web_search_usd_per_1000: float = Field(ge=0)


class PriceTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    verified: date
    sources: dict[str, str]
    modifiers: Modifiers
    models: dict[str, ModelPrice]
    sha256: str = Field(description="Digest of the table file, recorded in run bundles.")

    def price_for(self, model: str) -> ModelPrice | None:
        return self.models.get(normalise_model(model))

    def describe(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "verified": self.verified.isoformat(),
            "sources": dict(self.sources),
            "sha256": self.sha256,
        }


def normalise_model(model: str) -> str:
    """`anthropic/claude-opus-5-20260401` -> `claude-opus-5`."""
    return _DATE_SUFFIX.sub("", _PROVIDER_PREFIX.sub("", model.strip().lower()))


@cache
def load_price_table() -> PriceTable:
    text = resources.files("agent_canary").joinpath("data/prices.toml").read_text()
    return PriceTable.model_validate({**tomllib.loads(text), "sha256": sha256_text(text)})


# One request that is in flight when a trial crosses its dollar cap: the harness prefix written
# to a cold cache (about 16k tokens measured in spike 0001, rounded up) plus a long reply.
INFLIGHT_PROMPT_TOKENS = 20_000
INFLIGHT_OUTPUT_TOKENS = 4_000


def one_request_usd(model: str | None, table: PriceTable | None = None) -> float | None:
    """Estimated cost of one such request at the table's prices; None for an unknown model.

    An estimate, not a bound: a request can carry more context or a longer reply.
    """
    price = (table or load_price_table()).price_for(model) if model else None
    if price is None:
        return None
    return (
        INFLIGHT_PROMPT_TOKENS * price.cache_write_5m + INFLIGHT_OUTPUT_TOKENS * price.output
    ) / _MTOK


@dataclass(frozen=True)
class Usage:
    """Token usage for one model, in the four categories that are priced differently."""

    uncached_input: int = 0
    cache_write_5m: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    output: int = 0
    web_searches: int = 0
    us_only: bool = False
    largest_prompt: int = 0

    @property
    def cache_write(self) -> int:
        return self.cache_write_5m + self.cache_write_1h

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.uncached_input + other.uncached_input,
            self.cache_write_5m + other.cache_write_5m,
            self.cache_write_1h + other.cache_write_1h,
            self.cache_read + other.cache_read,
            self.output + other.output,
            self.web_searches + other.web_searches,
            self.us_only,
            max(self.largest_prompt, other.largest_prompt),
        )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def usage_from_trajectory(trajectory: dict[str, Any]) -> dict[tuple[str, bool], Usage] | None:
    """Sum per-request usage from ATIF step metrics, keyed by (model, US-only inference).

    Returns None if the transcript has no usage, or if any request cannot be priced from this
    table (no model name, or a non-standard speed).
    """
    default_model = (trajectory.get("agent") or {}).get("model_name")
    totals: dict[tuple[str, bool], Usage] = defaultdict(Usage)
    for step in trajectory.get("steps") or []:
        metrics = step.get("metrics") if isinstance(step, dict) else None
        if not isinstance(metrics, dict):
            continue
        model = step.get("model_name") or default_model
        extra = _dict(metrics.get("extra"))
        if (
            not isinstance(model, str)
            or extra.get("speed") not in (None, "standard")
            or extra.get("service_tier") not in (None, "standard", "default")
        ):
            return None
        prompt = _int(metrics.get("prompt_tokens"))
        cache_read = _int(metrics.get("cached_tokens"))
        # Harbor's Claude Code adapter names this cache_creation_input_tokens; its Codex
        # adapter, cache_write_input_tokens.
        written = _int(
            extra.get("cache_creation_input_tokens", extra.get("cache_write_input_tokens"))
        )
        by_ttl = _dict(extra.get("cache_creation"))
        write_1h = min(_int(by_ttl.get("ephemeral_1h_input_tokens")), written)
        searches = _dict(extra.get("server_tool_use"))
        us_only = extra.get("inference_geo") == "us"
        totals[(model, us_only)] += Usage(
            # ATIF prompt_tokens is everything sent: uncached, cache writes and cache reads.
            uncached_input=max(prompt - cache_read - written, 0),
            cache_write_5m=written - write_1h,  # a write with no TTL breakdown is a 5-minute one
            cache_write_1h=write_1h,
            cache_read=cache_read,
            output=_int(metrics.get("completion_tokens")),
            web_searches=_int(searches.get("web_search_requests")),
            us_only=us_only,
            largest_prompt=prompt,
        )
    return dict(totals) or None


@dataclass(frozen=True)
class PricedTrial:
    cost_usd: float
    cache_write_tokens: int


def price_trajectory(
    trajectory: dict[str, Any], table: PriceTable | None = None
) -> PricedTrial | None:
    """Dollars for one trial at the table's prices, or None if any part of it is not covered."""
    table = table or load_price_table()
    usage = usage_from_trajectory(trajectory)
    if usage is None:
        return None
    total = 0.0
    for (model, us_only), u in usage.items():
        price = table.price_for(model)
        if price is None:
            return None
        if price.long_context_tokens is not None and u.largest_prompt > price.long_context_tokens:
            return None
        tokens = (
            u.uncached_input * price.input
            + u.cache_write_5m * price.cache_write_5m
            + u.cache_write_1h * price.cache_write_1h
            + u.cache_read * price.cache_read
            + u.output * price.output
        ) / _MTOK
        total += tokens * (table.modifiers.inference_geo_us_multiplier if us_only else 1.0)
        total += u.web_searches * table.modifiers.web_search_usd_per_1000 / 1000
    return PricedTrial(
        cost_usd=round(total, 8), cache_write_tokens=sum(u.cache_write for u in usage.values())
    )
