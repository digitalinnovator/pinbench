Bug report for the contact book in `/app`: users end up with duplicate contacts. "José" typed
with a precomposed é and typed as e plus a combining accent is stored twice, and so are emails
that differ only in letter case or in surrounding spaces.

The code is in `/app/contacts.py` (class `ContactBook`, exception `DuplicateContact`) and
`/app/keys.py` (dedupe key helpers). Fix it so that all of these rules hold, keeping the public
names and signatures:

- Two contacts are duplicates when their names are equal and their emails are equal. A book
  never holds two duplicates. Duplicate checks use each contact's current name and email only.
- Names are equal when they match after Unicode NFC normalisation and then `str.casefold()`.
- Emails are equal when they match after stripping surrounding whitespace and then `str.casefold()`.
- `add(name, email)` returns the id of the existing duplicate and leaves that contact
  unchanged; otherwise it stores a new contact and returns its id. `len(book)` counts contacts.
- `update(contact_id, name=None, email=None)` replaces the fields that are not `None` and keeps
  the others. If the result would duplicate a different contact it raises `DuplicateContact`
  and changes nothing. An unknown id raises `KeyError`.
- `rename_domain(old, new)` replaces the domain (the part after the last `@`) with `new` in
  every contact whose domain equals `old` by the email rule, and returns how many contacts it
  changed. If a changed contact would duplicate another contact of the resulting book, it
  raises `DuplicateContact` and changes nothing.
- `get(contact_id)` returns the current `(name, email)`: values stay exactly as passed to `add`
  and `update`, and `rename_domain` changes only the domain.

The visible test is `/app/test_contacts.py`; run it with `python -m pytest -q`.
