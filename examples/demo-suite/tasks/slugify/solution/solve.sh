#!/bin/bash
cat > /app/text.py <<'EOF'
import re
import unicodedata

_MAX = 60


def slugify(title: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if len(slug) > _MAX:
        cut = slug.rfind("-", 0, _MAX + 1)
        slug = slug[:cut] if cut > 0 else slug[:_MAX]
    slug = slug.strip("-")
    return slug or "n-a"
EOF
