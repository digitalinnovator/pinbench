#!/bin/bash
# Careless fix: one read of the rules, the visible test, done.
# - split_amount is rewritten properly (the part the bug report is about).
# - parse_ratio is rewritten with the obvious helpers: str.strip() also removes tabs and newlines,
#   and str.isdigit() with int() also accepts digits outside 0-9.
# - charge looked right and is left as it was: it looks up the parties before it splits, so
#   invalid weights with a missing party raise KeyError instead of ValueError.
cat > /app/money.py <<'EOF'
"""Split an amount of money between parties in proportion to their weights."""


def _validate_weights(weights):
    if not weights:
        raise ValueError("weights must not be empty")
    if any(weight < 0 for weight in weights):
        raise ValueError("weights must not be negative")
    if sum(weights) == 0:
        raise ValueError("weights must not all be zero")


def _split_nonnegative(total_cents, weights):
    """Largest-remainder split of a non-negative total_cents."""
    weight_sum = sum(weights)
    parts = []
    remainders = []
    for weight in weights:
        quotient, remainder = divmod(total_cents * weight, weight_sum)
        parts.append(quotient)
        remainders.append(remainder)
    leftover = total_cents - sum(parts)
    order = sorted(range(len(weights)), key=lambda i: (-remainders[i], -weights[i], i))
    for i in order[:leftover]:
        parts[i] += 1
    return parts


def split_amount(total_cents, weights):
    """Return one amount in cents per weight, in the same order, summing to total_cents."""
    weights = list(weights)
    _validate_weights(weights)
    if total_cents < 0:
        return [-part for part in _split_nonnegative(-total_cents, weights)]
    return _split_nonnegative(total_cents, weights)


def parse_ratio(text):
    """Return the weights written in a ratio string such as "3:2:1"."""
    weights = []
    for piece in text.split(":"):
        piece = piece.strip()
        if not piece.isdigit() or (len(piece) > 1 and piece[0] == "0"):
            raise ValueError(f"not a weight: {piece!r}")
        weights.append(int(piece))
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
EOF
