from contacts import ContactBook


def test_composed_and_decomposed_name_is_one_contact():
    book = ContactBook()
    first = book.add("José", "jose@example.com")
    assert book.add("José", "jose@example.com") == first
    assert len(book) == 1
