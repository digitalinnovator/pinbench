"""Split an amount of money between parties in proportion to their weights."""

import math
import re

_WEIGHT = re.compile(r"\s*(0|[1-9][0-9]*)\s*")


def _shares(total_cents, weights):
    """Each party's share of total_cents before rounding."""
    weight_sum = sum(weights)
    if weight_sum == 0:
        raise ValueError("weights must not all be zero")
    return [total_cents * weight / weight_sum for weight in weights]


def _hand_out_leftover(parts, leftover):
    """Give the cents that rounding left over to the last party."""
    parts[-1] += leftover


def split_amount(total_cents, weights):
    """Return one amount in cents per weight, in the same order, summing to total_cents."""
    if total_cents == 0:
        return [0] * len(weights)
    if any(weight < 0 for weight in weights):
        raise ValueError("weights must not be negative")
    shares = _shares(total_cents, weights)
    parts = [math.floor(share) for share in shares]
    _hand_out_leftover(parts, total_cents - sum(parts))
    return parts


def parse_ratio(text):
    """Return the weights written in a ratio string such as "3:2:1"."""
    weights = []
    for piece in text.split(":"):
        match = _WEIGHT.fullmatch(piece)
        if match is None:
            raise ValueError(f"not a weight: {piece!r}")
        weights.append(int(match.group(1)))
    return weights


def charge(balances, total_cents, weights):
    """Add each party's part of total_cents to its entry in balances, or change nothing.

    balances maps a party name to the cents it owes; weights maps a party name to its weight.
    """
    for name in weights:
        if name not in balances:
            raise KeyError(name)
    parts = split_amount(total_cents, list(weights.values()))
    for name, part in zip(weights, parts):
        balances[name] += part
