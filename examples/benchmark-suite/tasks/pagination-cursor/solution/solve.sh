#!/bin/bash
cat > /app/pager.py <<'PY'
"""Cursor pagination over a Store."""


def _position(row):
    return (row["created_at"], row["id"])


def _cursor_position(cursor, order):
    """Return the (created_at, id) that the cursor "<order>:<created_at>:<id>" names.

    The id may hold any characters, so only the first two colons separate the parts. The
    created_at part must be written exactly as str() writes the integer.
    """
    if not isinstance(cursor, str):
        raise ValueError(f"cursor is not a string: {cursor!r}")
    parts = cursor.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"malformed cursor: {cursor!r}")
    cursor_order, text, id = parts
    if cursor_order != order:
        raise ValueError(f"cursor is for order {cursor_order!r}, not {order!r}")
    try:
        created_at = int(text)
    except ValueError:
        raise ValueError(f"malformed cursor: {cursor!r}") from None
    if str(created_at) != text:
        raise ValueError(f"malformed cursor: {cursor!r}")
    return (created_at, id)


def _rows_after(store, cursor, order):
    """Return the rows in `order` that sort after `cursor`, or every row when it is None."""
    if order not in ("asc", "desc"):
        raise ValueError(f"unknown order: {order!r}")
    rows = sorted(store.scan(), key=_position, reverse=order == "desc")
    if cursor is None:
        return rows
    after = _cursor_position(cursor, order)
    if order == "asc":
        return [row for row in rows if _position(row) > after]
    return [row for row in rows if _position(row) < after]


def fetch_page(store, limit, cursor=None, order="asc"):
    """Return (rows, next_cursor) for one page of at most `limit` rows."""
    rows = _rows_after(store, cursor, order)
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        created_at, id = _position(page[-1])
        next_cursor = f"{order}:{created_at}:{id}"
    return page, next_cursor


def remaining(store, cursor=None, order="asc"):
    """Return how many rows come after `cursor`, or how many rows there are when it is None."""
    return len(_rows_after(store, cursor, order))
PY
