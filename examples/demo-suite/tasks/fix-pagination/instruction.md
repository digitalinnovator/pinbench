`/app/pagination.py` defines `paginate(items, page, per_page)`. Pages are meant to be
1-indexed, but callers report that page 1 skips the first items.

Fix the function so that:

- `page=1` returns the first `per_page` items, `page=2` the next ones, and so on.
- A page past the end returns an empty list.
- It raises `ValueError` when `page` or `per_page` is less than 1.

Keep the function name and signature unchanged.
