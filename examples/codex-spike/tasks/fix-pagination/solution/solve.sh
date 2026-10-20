#!/bin/bash
cat > /app/pagination.py <<'EOF'
def paginate(items, page, per_page):
    """Return the items on the given 1-indexed page."""
    if page < 1 or per_page < 1:
        raise ValueError("page and per_page must be >= 1")
    start = (page - 1) * per_page
    return items[start : start + per_page]
EOF
