`slugify(title)` in `/app/text.py` is used to build URL slugs, but it only lowercases and
swaps spaces for hyphens. Rewrite it so that it:

1. Transliterates accented Latin letters to plain ASCII (`é` → `e`, `Ü` → `u`) and drops
   any other non-ASCII characters.
2. Lowercases the result.
3. Replaces every run of characters other than `a–z` and `0–9` with a single hyphen.
4. Strips leading and trailing hyphens.
5. Returns `"n-a"` if nothing is left.
6. Limits the slug to 60 characters. If it is longer, cut it at the last hyphen at or before
   position 60 when there is one, otherwise hard-cut at 60. Never end with a hyphen.

Only the standard library is available.
