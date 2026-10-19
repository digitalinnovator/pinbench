"""Dedupe keys: two contacts are duplicates when their keys are equal."""


def name_key(name: str) -> str:
    return name.lower()


def email_key(email: str) -> str:
    return email


def contact_key(name: str, email: str) -> tuple[str, str]:
    return (name_key(name), email_key(email))
