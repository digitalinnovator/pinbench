"""Cursor pagination over a Store."""


def fetch_page(store, limit, cursor=None, order="asc"):
    """Return (rows, next_cursor) for one page of at most `limit` rows."""
    if order not in ("asc", "desc"):
        raise ValueError(f"unknown order: {order!r}")
    rows = store.scan()
    if order == "desc":
        rows.sort(key=lambda row: row["created_at"], reverse=True)
    if cursor is not None:
        if order == "asc":
            rows = [row for row in rows if row["created_at"] > cursor]
        else:
            rows = [row for row in rows if row["created_at"] < cursor]
    page = rows[:limit]
    next_cursor = page[-1]["created_at"] if page else None
    return page, next_cursor


def remaining(store, cursor=None, order="asc"):
    """Return how many rows come after `cursor`."""
    rows = store.scan()
    if cursor is None:
        return len(rows)
    if order == "asc":
        return len([row for row in rows if row["created_at"] > cursor])
    return len([row for row in rows if row["created_at"] < cursor])
