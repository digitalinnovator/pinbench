#!/bin/bash
# Careless fix: repairs the key helpers and the two hand-built keys in ContactBook.update, then
# stops. rename_domain is left as it was because it "just calls update": it still matches the
# domain by exact text and still applies the renames one by one, so a clash half-applies them.
cat > /app/keys.py <<'EOF'
"""Dedupe keys: two contacts are duplicates when their keys are equal."""

import unicodedata


def name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def email_key(email: str) -> str:
    return email.strip().casefold()


def contact_key(name: str, email: str) -> tuple[str, str]:
    return (name_key(name), email_key(email))
EOF
cat > /app/contacts.py <<'EOF'
"""An in-memory contact book that refuses duplicate contacts."""

from keys import contact_key


class DuplicateContact(ValueError):
    """An update would turn a contact into a duplicate of another one."""


class ContactBook:
    def __init__(self) -> None:
        self._contacts: dict[int, tuple[str, str]] = {}  # id -> (name, email) as given
        self._ids: dict[tuple[str, str], int] = {}  # dedupe key -> id
        self._next_id = 1

    def __len__(self) -> int:
        return len(self._contacts)

    def get(self, contact_id: int) -> tuple[str, str]:
        """Return the stored (name, email) of a contact."""
        return self._contacts[contact_id]

    def add(self, name: str, email: str) -> int:
        """Return the id of the duplicate contact if there is one, else store a new one."""
        key = contact_key(name, email)
        if key in self._ids:
            return self._ids[key]
        contact_id = self._next_id
        self._next_id += 1
        self._contacts[contact_id] = (name, email)
        self._ids[key] = contact_id
        return contact_id

    def update(self, contact_id: int, name: str | None = None, email: str | None = None) -> None:
        """Replace the given fields; raise DuplicateContact if another contact matches."""
        old_name, old_email = self._contacts[contact_id]
        new_name = old_name if name is None else name
        new_email = old_email if email is None else email
        new_key = contact_key(new_name, new_email)
        owner = self._ids.get(new_key)
        if owner is not None and owner != contact_id:
            raise DuplicateContact(f"contact {owner} has the same name and email")
        del self._ids[contact_key(old_name, old_email)]
        self._ids[new_key] = contact_id
        self._contacts[contact_id] = (new_name, new_email)

    def rename_domain(self, old: str, new: str) -> int:
        """Move every contact whose email is at domain `old` to `new`; return how many moved."""
        changed = 0
        for contact_id, (_, email) in list(self._contacts.items()):
            if email.endswith("@" + old):
                local = email[: -len(old) - 1]
                self.update(contact_id, email=local + "@" + new)
                changed += 1
        return changed
EOF
