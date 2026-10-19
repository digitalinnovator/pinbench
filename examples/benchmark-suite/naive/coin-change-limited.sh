#!/bin/bash
# Careless solution: the search and all three preferences are right, but it stops at the obvious
# code. The result comes out largest denomination first instead of in the inventory's order, the
# reserve is a plain subtraction (a denomination below the reserve then blocks every payout), and
# pay_out subtracts as it goes, so a payout that fails part of the way through leaves the
# inventory changed.
cat > /app/coins.py <<'PY'
from functools import lru_cache


def make_change(amount, inventory, reserve=0):
    """Pick coins from `inventory` that sum to `amount`; None when that is impossible."""
    denominations = sorted(inventory, reverse=True)

    @lru_cache(maxsize=None)
    def best(index, rest):
        """Best (coins, denominations, negated counts) for `rest` from denominations[index:]."""
        if index == len(denominations):
            return (0, 0, ()) if rest == 0 else None
        coin = denominations[index]
        usable = inventory[coin] - reserve
        winner = None
        for used in range(min(usable, rest // coin) + 1):
            tail = best(index + 1, rest - used * coin)
            if tail is None:
                continue
            key = (used + tail[0], (used > 0) + tail[1], (-used, *tail[2]))
            if winner is None or key < winner:
                winner = key
        return winner

    key = best(0, amount)
    if key is None:
        return None
    return {coin: -negated for coin, negated in zip(denominations, key[2]) if negated}


def pay_out(amounts, inventory, reserve=0):
    """Pay each amount in turn out of `inventory`; None when one of them cannot be paid."""
    results = []
    for amount in amounts:
        result = make_change(amount, inventory, reserve)
        if result is None:
            return None
        for coin, used in result.items():
            inventory[coin] -= used
        results.append(result)
    return results
PY
