Implement `make_change(amount, inventory, reserve=0)` and
`pay_out(amounts, inventory, reserve=0)` in `/app/coins.py`. They pay out exact amounts from a
limited stock of coins. A small visible test is in `/app/test_coins.py`.

`amount` is a non-negative integer and `amounts` is a list of such amounts. `inventory` is a dict
(possibly empty, keys in no particular order) that maps each coin denomination, a positive
integer, to the number of coins of it in stock, a non-negative integer. `reserve` is a
non-negative integer. Inputs are always valid, so no validation is needed.

`make_change` returns a dict that maps denomination to the number of coins used:
- The coins sum to exactly `amount`. For an amount of 0 return `{}`.
- Of each denomination, `reserve` coins are held back; only the coins in stock beyond those
  may be used. A denomination that holds `reserve` coins or fewer cannot be used.
- The result contains only the denominations that are used at least once, and its keys are in
  the same order as they appear in `inventory`.
- Use as few coins in total as possible.
- When several solutions use the same fewest number of coins, prefer the one that uses fewer
  different denominations.
- If they still tie, prefer the one that uses more coins of the largest denomination in the
  inventory; if they use equally many of it, prefer more of the next largest, and so on down.
- Return `None` when no selection of the usable coins sums to `amount`.
- Do not modify `inventory`.

`pay_out` pays several amounts out of the same stock:
- Pay the amounts in the given order, each by the `make_change` rules with the same `reserve`,
  from the stock that the earlier payouts left. Return the list of the results, one per amount.
- Subtract the paid coins from `inventory` in place. A denomination that runs out stays in
  `inventory` with a count of 0.
- If any of the amounts cannot be paid, return `None` and leave `inventory` as it was.
