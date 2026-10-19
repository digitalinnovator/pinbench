`/app/money.py` splits money between parties. Bug report: `split_amount(10, [1, 1, 1, 0])`
returns `[3, 3, 3, 1]` instead of `[4, 3, 3, 0]`, so a party with weight 0 is charged a cent.
Fix `/app/money.py` so that every rule below holds. `/app/test_money.py` must keep passing.

`split_amount(total_cents, weights)`:
- `total_cents` is an int of any size and `weights` is any iterable of ints of any size.
  Return a list of ints, one part per weight in the same order, that sums exactly to `total_cents`.
- For `total_cents >= 0`, use the largest-remainder method. A party's exact share is
  `total_cents * weight / sum(weights)`. Each party first gets its exact share rounded down. The
  cents left over go, one each, to the parties whose exact shares have the largest fractional parts.
- Among equal fractional parts, the party with the larger weight goes first; if the weights
  are also equal, the party earlier in `weights` goes first.
- A negative `total_cents` is a refund: each party is refunded exactly the amount it is
  charged for the positive total of the same size.
- A party with weight 0 always gets 0.
- Invalid weights always raise `ValueError`: empty `weights`, a negative weight, or all weights 0.

`parse_ratio(text)` returns, as a list of ints, the weights in a ratio string such as `"3:2:1"`:
- The string is one or more weights separated by `:`. A weight is `0`, or one or more ASCII
  digits `0`-`9` of which the first is not `0`.
- Any number of spaces (the character `" "`) may come before and after each weight.
- Any other string raises `ValueError`.

`charge(balances, total_cents, weights)` takes two dicts keyed by party name: `balances` holds
the cents each party owes and `weights` holds each party's weight.
- It splits `total_cents` with `split_amount`, passing the values of `weights` in dict order,
  and adds each part to that party's entry in `balances`. It changes no other entry.
- A party in `weights` that is missing from `balances` raises `KeyError`.
- Invalid weights raise `ValueError`, whether or not a party is missing from `balances`.
- Whenever `charge` raises, `balances` is left exactly as it was.
