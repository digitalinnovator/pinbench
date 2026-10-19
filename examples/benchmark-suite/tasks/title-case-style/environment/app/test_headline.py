from headline import headline_case


def test_example():
    assert headline_case("the lord of the rings") == "The Lord of the Rings"
    assert headline_case("war and peace") == "War and Peace"
