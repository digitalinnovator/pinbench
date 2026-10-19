#!/bin/bash
cat > /app/coins.py <<'PY'
from functools import lru_cache

# A solution is ranked by (coins, different denominations, negated counts from the largest
# denomination down); the smallest key is the preferred solution under all three rules.
Key = tuple[int, int, tuple[int, ...]]


def make_change(
    amount: int, inventory: dict[int, int], reserve: int = 0
) -> dict[int, int] | None:
    """Pick coins from `inventory` that sum to `amount`; None when that is impossible."""
    # Only the coins above the reserve count. A denomination at or below the reserve is left out
    # altogether: it must not take part, and it must not stop the other denominations either.
    usable = {coin: stock - reserve for coin, stock in inventory.items() if stock > reserve}
    denominations = sorted(usable, reverse=True)

    @lru_cache(maxsize=None)
    def best(index: int, rest: int) -> Key | None:
        """Smallest key that makes `rest` from denominations[index:], or None."""
        if index == len(denominations):
            return (0, 0, ()) if rest == 0 else None
        coin = denominations[index]
        winner: Key | None = None
        for used in range(min(usable[coin], rest // coin) + 1):
            tail = best(index + 1, rest - used * coin)
            if tail is None:
                continue
            # Each part of the key only adds to, or is prefixed onto, the tail's key, so the
            # best tail for a given `used` is also the best overall for that `used`.
            key = (used + tail[0], (used > 0) + tail[1], (-used, *tail[2]))
            if winner is None or key < winner:
                winner = key
        return winner

    key = best(0, amount)
    if key is None:
        return None
    used = {coin: -negated for coin, negated in zip(denominations, key[2])}
    # The search works largest first; the result follows the inventory's own key order.
    return {coin: used[coin] for coin in inventory if used.get(coin)}


def pay_out(
    amounts: list[int], inventory: dict[int, int], reserve: int = 0
) -> list[dict[int, int]] | None:
    """Pay each amount in turn out of `inventory`; None when one of them cannot be paid."""
    # Work on a copy and write it back only once every amount is paid, so that a payout that
    # fails part of the way through leaves `inventory` untouched.
    stock = dict(inventory)
    results: list[dict[int, int]] = []
    for amount in amounts:
        result = make_change(amount, stock, reserve)
        if result is None:
            return None
        for coin, used in result.items():
            stock[coin] -= used
        results.append(result)
    inventory.update(stock)
    return results
PY
