import sys

import pytest

sys.path.insert(0, "/app")
from contacts import ContactBook, DuplicateContact  # noqa: E402

COMPOSED = "José"  # one code point for the accented letter
DECOMPOSED = "José"  # plain e followed by a combining acute accent


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (("Ann Lee", "ann@example.com"), ("Ann Lee", "ann@work.example")),
        (("Ann Lee", "ann@example.com"), ("Ann Li", "ann@example.com")),
    ],
)
def test_add_keeps_contacts_that_differ(first, second):
    book = ContactBook()
    assert book.add(*first) != book.add(*second)
    assert len(book) == 2


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ((COMPOSED, "jose@example.com"), (DECOMPOSED, "jose@example.com")),
        ((DECOMPOSED, "jose@example.com"), (COMPOSED, "jose@example.com")),
        (("Ann Lee", "ann@example.com"), ("ANN lee", "ann@example.com")),
        (("Ann Lee", "Ann.Lee@Example.COM"), ("Ann Lee", "ann.lee@example.com")),
        (("Ann Lee", "ann@example.com"), ("Ann Lee", "  ann@example.com ")),
        ((DECOMPOSED, " Jose@Example.com "), ("JOSÉ", "jose@example.com")),
    ],
)
def test_add_returns_the_existing_duplicate(first, second):
    book = ContactBook()
    contact_id = book.add(*first)
    assert book.add(*second) == contact_id
    assert len(book) == 1


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (("Hans Straße", "hans@example.com"), ("HANS STRASSE", "hans@example.com")),
        (("Hans", "weiß@example.com"), ("Hans", "WEISS@example.com")),
    ],
)
def test_add_compares_with_casefold(first, second):
    book = ContactBook()
    contact_id = book.add(*first)
    assert book.add(*second) == contact_id
    assert len(book) == 1


def test_get_returns_values_as_first_added():
    book = ContactBook()
    contact_id = book.add(DECOMPOSED, " Jose@Example.com ")
    assert book.get(contact_id) == (DECOMPOSED, " Jose@Example.com ")
    assert book.add(COMPOSED.upper(), "jose@example.com") == contact_id
    assert book.get(contact_id) == (DECOMPOSED, " Jose@Example.com ")


def test_update_replaces_only_the_given_fields():
    book = ContactBook()
    contact_id = book.add("Ann Lee", "ann@example.com")
    book.update(contact_id, email="Ann@Work.example")
    assert book.get(contact_id) == ("Ann Lee", "Ann@Work.example")
    book.update(contact_id, name="Ann Li")
    assert book.get(contact_id) == ("Ann Li", "Ann@Work.example")
    assert len(book) == 1


def test_update_unknown_id_raises_key_error():
    book = ContactBook()
    book.add("Ann Lee", "ann@example.com")
    with pytest.raises(KeyError):
        book.update(99, name="Bob Ray")


def test_update_rejects_a_duplicate_of_another_contact():
    book = ContactBook()
    first = book.add("Ann Lee", "ann@example.com")
    second = book.add("Bob Ray", "ann@example.com")
    with pytest.raises(DuplicateContact):
        book.update(second, name="ann lee")
    assert book.get(first) == ("Ann Lee", "ann@example.com")
    assert book.get(second) == ("Bob Ray", "ann@example.com")
    assert len(book) == 2


def test_update_to_the_contacts_own_name_in_other_case_is_allowed():
    book = ContactBook()
    contact_id = book.add("Ann Lee", "ann@example.com")
    book.update(contact_id, name="ANN LEE")
    assert book.get(contact_id) == ("ANN LEE", "ann@example.com")
    assert len(book) == 1


def test_old_values_stop_counting_after_update():
    book = ContactBook()
    contact_id = book.add("Ann Lee", "ann@example.com")
    book.update(contact_id, name="Ann Li")
    assert book.add("ANN LEE", "Ann@example.com") != contact_id
    assert len(book) == 2


def test_update_rejects_an_equivalent_spelling_of_another_contact():
    book = ContactBook()
    book.add(COMPOSED, "jose@example.com")
    second = book.add("Joe", "joe@example.com")
    with pytest.raises(DuplicateContact):
        book.update(second, name=DECOMPOSED, email=" JOSE@example.com ")
    assert book.get(second) == ("Joe", "joe@example.com")
    assert book.add("JOE", "joe@example.com") == second
    assert len(book) == 2


def test_updated_contact_is_found_by_an_equivalent_spelling():
    book = ContactBook()
    contact_id = book.add("Joe", "joe@example.com")
    book.update(contact_id, name=DECOMPOSED, email=" Jose@Example.com")
    assert book.add(COMPOSED, "jose@example.com") == contact_id
    assert len(book) == 1


def test_update_of_a_contact_added_in_another_spelling():
    book = ContactBook()
    contact_id = book.add(DECOMPOSED, " jose@example.com ")
    book.update(contact_id, email="jose@work.example")
    assert book.get(contact_id) == (DECOMPOSED, "jose@work.example")
    assert book.add(COMPOSED, "JOSE@work.example") == contact_id
    assert book.add(COMPOSED, "jose@example.com") != contact_id
    assert len(book) == 2


def test_rename_domain_moves_the_matching_contacts_and_counts_them():
    book = ContactBook()
    ann = book.add("Ann Lee", "ann@old.example")
    bob = book.add("Bob Ray", "Bob.Ray@old.example")
    cy = book.add("Cy Orr", "cy@mail.old.example")
    dee = book.add("Dee Poe", "dee@other.example")
    assert book.rename_domain("old.example", "new.example") == 2
    assert book.get(ann) == ("Ann Lee", "ann@new.example")
    assert book.get(bob) == ("Bob Ray", "Bob.Ray@new.example")
    assert book.get(cy) == ("Cy Orr", "cy@mail.old.example")
    assert book.get(dee) == ("Dee Poe", "dee@other.example")
    assert len(book) == 4


def test_renamed_contact_is_a_duplicate_under_the_new_domain_only():
    book = ContactBook()
    ann = book.add("Ann Lee", "ann@old.example")
    assert book.rename_domain("old.example", "new.example") == 1
    assert book.add("ANN LEE", " Ann@New.Example") == ann
    assert book.add("Ann Lee", "ann@old.example") != ann
    assert len(book) == 2
    assert book.rename_domain("none.example", "new.example") == 0
    assert len(book) == 2


@pytest.mark.parametrize(
    ("email", "old"),
    [
        ("ann@Old.Example", "old.example"),
        ("ann@old.example ", "old.example"),
        ("ann@old.example", " OLD.Example "),
    ],
)
def test_rename_domain_matches_the_domain_by_the_email_rule(email, old):
    book = ContactBook()
    ann = book.add("Ann Lee", email)
    assert book.rename_domain(old, "new.example") == 1
    assert book.add("Ann Lee", "ann@new.example") == ann
    assert len(book) == 1


def test_rename_domain_that_would_duplicate_changes_nothing():
    book = ContactBook()
    ann = book.add("Ann Lee", "ann@old.example")
    bob = book.add("Bob Ray", "bob@old.example")
    cy = book.add("Cy Orr", "cy@old.example")
    other = book.add("Bob Ray", "bob@new.example")
    with pytest.raises(DuplicateContact):
        book.rename_domain("old.example", "new.example")
    assert book.get(ann) == ("Ann Lee", "ann@old.example")
    assert book.get(bob) == ("Bob Ray", "bob@old.example")
    assert book.get(cy) == ("Cy Orr", "cy@old.example")
    assert book.get(other) == ("Bob Ray", "bob@new.example")
    assert book.add("Ann Lee", "ann@old.example") == ann
    assert book.add("Cy Orr", "cy@old.example") == cy
    assert len(book) == 4
