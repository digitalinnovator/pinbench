#!/bin/bash
cat > /app/money.py <<'EOF'
"""Split an amount of money between parties in proportion to their weights."""

import re

# A weight is 0 or ASCII digits with no leading zero, with only the space character around it.
# "\s" and "\d" would also accept tabs, newlines and digits outside 0-9.
_WEIGHT = re.compile(r" *(0|[1-9][0-9]*) *")


def _check_weights(weights):
    if not weights:
        raise ValueError("weights must not be empty")
    if any(weight < 0 for weight in weights):
        raise ValueError("weights must not be negative")
    if sum(weights) == 0:
        raise ValueError("weights must not all be zero")


def _split_non_negative(amount, weights):
    """Largest-remainder split of amount >= 0 in integer arithmetic, so it is exact."""
    weight_sum = sum(weights)
    parts = [amount * weight // weight_sum for weight in weights]
    remainders = [amount * weight % weight_sum for weight in weights]
    leftover = amount - sum(parts)
    # Largest remainder first; among equal remainders the larger weight, then the earlier party.
    order = sorted(range(len(weights)), key=lambda i: (-remainders[i], -weights[i], i))
    for i in order[:leftover]:
        parts[i] += 1
    return parts


def split_amount(total_cents, weights):
    """Return one amount in cents per weight, in the same order, summing to total_cents."""
    weights = list(weights)  # weights may be a one-shot iterable; read it exactly once
    _check_weights(weights)
    if total_cents < 0:
        # A refund mirrors the charge: split the positive amount, then negate every part.
        return [-part for part in _split_non_negative(-total_cents, weights)]
    return _split_non_negative(total_cents, weights)


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
    names = list(weights)
    # Split first: invalid weights raise ValueError whether or not a party is missing.
    parts = split_amount(total_cents, [weights[name] for name in names])
    # Check every party before the first update, so a failure leaves balances untouched.
    for name in names:
        if name not in balances:
            raise KeyError(name)
    for name, part in zip(names, parts):
        balances[name] += part
EOF
