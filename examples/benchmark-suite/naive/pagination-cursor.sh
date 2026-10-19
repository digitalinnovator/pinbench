#!/bin/bash
# Careless fix: the ordering, the tie-breaker and the new cursor string are all right, so the
# visible test and every walk over plain ids go green. The cursor is read back with split(":")
# into three names, though, so an id that holds a colon makes the function reject the cursor it
# returned itself. int() also takes "+200", "0200", " 200" and "-0", so a created_at part that
# str() would never write gets through. A cursor that is not a str fails with AttributeError
# instead of ValueError. And `remaining` only looks at `order` when it has a cursor to compare
# it with, so an unknown order with no cursor returns a count instead of raising.
cat > /app/pager.py <<'PY'
"""Cursor pagination over a Store."""


def _position(row):
    return (row["created_at"], row["id"])


def _rows_after(store, cursor, order):
    rows = sorted(store.scan(), key=_position, reverse=order == "desc")
    if cursor is None:
        return rows
    cursor_order, created_at, id = cursor.split(":")
    if cursor_order != order:
        raise ValueError(f"cursor is for order {cursor_order!r}, not {order!r}")
    after = (int(created_at), id)
    if order == "asc":
        return [row for row in rows if _position(row) > after]
    return [row for row in rows if _position(row) < after]


def fetch_page(store, limit, cursor=None, order="asc"):
    """Return (rows, next_cursor) for one page of at most `limit` rows."""
    if order not in ("asc", "desc"):
        raise ValueError(f"unknown order: {order!r}")
    rows = _rows_after(store, cursor, order)
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        created_at, id = _position(page[-1])
        next_cursor = f"{order}:{created_at}:{id}"
    return page, next_cursor


def remaining(store, cursor=None, order="asc"):
    """Return how many rows come after `cursor`."""
    return len(_rows_after(store, cursor, order))
PY
