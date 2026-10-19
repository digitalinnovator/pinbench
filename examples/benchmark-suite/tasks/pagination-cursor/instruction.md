Users report that `fetch_page` in `/app/pager.py` skips rows on later pages when several rows
share the same `created_at`. Fix that file so that it meets the contract below. Rows come from
`Store` in `/app/store.py`. A row is a dict with an integer `created_at`, which may be negative,
and a unique `id`, which may be any `str`.

Rules for every `order` argument and every `cursor` argument:
- The `"asc"` order sorts rows by `created_at`, and rows with equal `created_at` by `id` as
  Python compares strings. The `"desc"` order is exactly the reverse of the `"asc"` order. Any
  other `order` raises `ValueError`.
- A cursor is the string `<order>:<created_at>:<id>`, such as `asc:200:k3` or `desc:-5:k3`. Its
  `created_at` part is exactly what Python's `str()` writes for that integer, and its `id` part
  is the id itself. A cursor names the position that a row with that `created_at` and `id` has
  in that order, whether or not the store holds such a row.
- A `cursor` that is not `None` raises `ValueError` unless it is a cursor whose order is the
  `order` argument.

`fetch_page(store, limit, cursor=None, order="asc")` returns `(rows, next_cursor)`:
- `rows` is a list. With `cursor=None` it holds the first `limit` rows in that order. With a
  cursor it holds the first `limit` rows that sort after the cursor's position. It holds fewer
  than `limit` rows only when fewer such rows exist.
- `next_cursor` is `None` when the returned page is empty or no rows remain after it. Otherwise
  it is the cursor made of `order` and the last row of the page.
- Following `next_cursor` from the first page until it is `None`, on an unchanged store, yields
  every row exactly once, in that order.

`remaining(store, cursor=None, order="asc")` returns the number of rows that sort after the
cursor's position in that order, or the number of all rows when `cursor` is `None`.

Keep `Store()`, `Store.add(id, created_at)` and `Store.delete(id)` working as they do now.
`limit` is always a positive integer. `/app/test_pager.py` has one test; run `python -m pytest -q`.
