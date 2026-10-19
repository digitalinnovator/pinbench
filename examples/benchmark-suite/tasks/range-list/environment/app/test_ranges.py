from ranges import compress, expand


def test_compress():
    assert compress([1, 2, 3, 5, 7, 8, 9]) == "1-3,5,7-9"


def test_expand():
    assert expand("1-3,5,7-9") == [1, 2, 3, 5, 7, 8, 9]
