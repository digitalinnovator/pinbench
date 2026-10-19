Implement `apply(order, event)` and `apply_all(order, events)` in `/app/events.py`.
`/app/orders.py` defines `Order` and `InvalidTransition`; do not edit it. `/app/test_events.py`
is a sample test (`python -m pytest -q`).

An event is a dict with a `"type"` and, for `pay` and `refund`, an `"amount"` in cents, such as
`{"type": "pay", "amount": 300}`. An event that is not allowed is rejected. Rules:

- `pay`: allowed only when `status` is `"new"`. Adds `amount` to `paid`. When `paid` equals `total`,
  `status` becomes `"paid"`; until then it stays `"new"`. Rejected if `paid` would exceed `total`.
- `ship`: allowed only when `status` is `"paid"`. `status` becomes `"shipped"`.
- `cancel`: allowed only when `status` is `"new"` or `"paid"`. `status` becomes `"cancelled"`.
- `refund`: allowed only when `status` is `"paid"`, `"shipped"` or `"cancelled"`. Adds `amount`
  to `refunded`; `status` stays the same. Rejected if `amount` is more than `paid` minus `refunded`.
- A `pay` or `refund` is rejected if its `amount` is missing or is not an `int` above zero; a
  `bool` is not accepted as an amount.
- An event with any other type, or with no `"type"` key, is rejected.
- An accepted event also appends its type, a string such as `"pay"`, to `history`.
- If an event has an `"id"` key, its value must be a string of one or more characters, each an
  ASCII letter, a digit `0`-`9`, `-` or `_`. An event with any other value there is rejected.
- An accepted event that has an id adds it to `seen`, spelled exactly as in the event.
- Two ids that differ only in the case of their letters are the same id. An event whose id is
  already in `seen` is ignored and no other rule applies to it: no change, no error, nothing
  appended to `history`.
- A rejected event raises `InvalidTransition` and leaves every field of the order as it was.
- `events` is any iterable of events, such as a list or a generator. `apply_all` applies them in
  order. If any of them is rejected, it raises `InvalidTransition` and leaves the order exactly
  as it was before the call.
- Other code holds references to an order's `history` list and `seen` set: both functions change
  these two objects in place and never replace them with new ones.
- Both functions return `None`.
