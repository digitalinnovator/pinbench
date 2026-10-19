Implement the `IntervalSet` class in `/app/interval_set.py`; a stub with the signatures is
there. It is a set of integers stored as half-open intervals `[lo, hi)`: `lo` is in the
interval and `hi` is not. `lo`, `hi` and `x` are always `int`s; they may be negative or very
large. A small visible test is in `/app/test_interval_set.py`.

Members:
- `IntervalSet()` creates an empty set.
- `add(lo, hi)` puts every integer of `[lo, hi)` into the set and returns how many integers
  were not in the set before.
- `remove(lo, hi)` takes every integer of `[lo, hi)` out of the set and returns how many
  integers it took out. Integers that are not in the set are ignored.
- `add_all(pairs)` adds every `(lo, hi)` pair of `pairs`. `pairs` is any iterable of pairs.
- `add_text(text)` adds every interval written in the string `text`.
- `contains(x)` returns `True` if the integer `x` is in the set and `False` if it is not.
- `intervals` is a property. It returns a new list of `(lo, hi)` tuples that together hold
  exactly the integers in the set.

Rules:
- The list from `intervals` is sorted by `lo` and is the shortest such list: no interval in
  it is empty, and no two of them can be replaced by one interval.
- If `lo == hi`, the interval is empty: `add` and `remove` leave the set unchanged and return 0.
- If `lo > hi`, `add` and `remove` raise `ValueError` and leave the set unchanged.
- `text` is the empty string, or one or more items joined by `,`, such as `"1:5, -3:0"`. An
  item is two decimal numbers written as `lo:hi`. A number is an optional `-` followed by one
  or more of the digits `0` to `9`. Any number of spaces (`" "`) may follow a `,`. The text
  has no other characters.
- `add_all` and `add_text` raise `ValueError` if any pair or item has `lo > hi`; `add_text`
  also raises it if `text` is not in the form above. When they raise, the set is unchanged.
- Changing a list that `intervals` returned does not change the set.
