def paginate(items, page, per_page):
    """Return the items on the given 1-indexed page."""
    start = page * per_page
    return items[start : start + per_page]
