from canonquery import canonical_query


def test_sorts_by_key():
    assert canonical_query("b=2&a=1") == "a=1&b=2"


def test_reencodes():
    assert canonical_query("q=%7e%2f") == "q=~%2F"
