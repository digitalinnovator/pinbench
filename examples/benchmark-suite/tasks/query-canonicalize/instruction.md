Implement `canonical_query(query: str) -> str` in `/app/canonquery.py`. It returns the canonical
form of a URL query string such as `b=2&a=1`. A small visible test is in
`/app/test_canonquery.py`.

Parsing:

- If the query starts with `?`, that one `?` is removed before anything else is done.
- The query is split at `&` into segments. Empty segments are dropped; the others are entries.
- An entry is split at its first `=` into a key and a value. An entry with no `=` has a key
  and no value.
- Keys and values are decoded to byte strings: each literal `+` becomes a space, each `%XX`
  sequence becomes the byte with that hex value, and every other character becomes its UTF-8
  bytes. A decoded string need not be valid UTF-8.
- A `%` must be followed by two hex digits, in upper or lower case. If any `%` in the query is
  not, the query is malformed and `canonical_query` raises `ValueError`.
- Leading and trailing space bytes (0x20) are then removed from each decoded key and value.

Output, using the keys and values as decoded and trimmed above:

- Two entries are duplicates when their keys are equal and either both have a value and the
  values are equal, or neither has a value. Of duplicates, only the last is kept.
- Entries are sorted by key in ascending lexicographic byte order. Entries with equal keys
  keep the order they had in the input.
- Keys and values are re-encoded byte by byte. The bytes of the ASCII characters `A-Z`, `a-z`,
  `0-9`, `-`, `.`, `_` and `~` are written as those characters. Every other byte is written as
  `%XX` with uppercase hex digits.
- An entry with a value is written `key=value`, also when the value is empty. An entry with
  no value is written as the key alone.
- Entries are joined with `&`. If there are no entries, the result is the empty string.
