import sys

import pytest

sys.path.insert(0, "/app")
from canonquery import canonical_query  # noqa: E402


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", ""),
        ("&a=1&&b=2&", "a=1&b=2"),
        ("a=&x=a=b", "a=&x=a%3Db"),
        ("=x", "=x"),
    ],
)
def test_splitting(query, expected):
    assert canonical_query(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("b=1&B=2&a-=3&a=4&_=5", "B=2&_=5&a=4&a-=3&b=1"),
        ("%62=1&a=2&caf%C3%A9=3&cafz=4", "a=2&b=1&cafz=4&caf%C3%A9=3"),
    ],
)
def test_sorted_by_decoded_key(query, expected):
    assert canonical_query(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("k=%41%2d%5F%2e%7E", "k=A-_.~"),
        ("u=a/b:c@d,e&name=é", "name=%C3%A9&u=a%2Fb%3Ac%40d%2Ce"),
        ("n=1%2B1&p=100%25&a%26b=c%3Dd", "a%26b=c%3Dd&n=1%2B1&p=100%25"),
        ("d=%2541&h=%4a%4A", "d=%2541&h=JJ"),
        ("first+name=John+Smith", "first%20name=John%20Smith"),
    ],
)
def test_decode_then_reencode(query, expected):
    assert canonical_query(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("t=b&s=1&t=a&t=c", "s=1&t=b&t=a&t=c"),
        ("k=1&k&k=&j", "j&k=1&k&k="),
    ],
)
def test_equal_keys_keep_input_order(query, expected):
    assert canonical_query(query) == expected


def test_bytes_that_are_not_utf8():
    assert canonical_query("%C3%A9=1&a=%FF&%80=2&a=%FE") == "a=%FF&a=%FE&%80=2&%C3%A9=1"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("a=1&%61=1", "a=1"),
        ("t=a&t=b&t=a", "t=b&t=a"),
        ("k&k=&k", "k=&k"),
    ],
)
def test_last_of_duplicates_is_kept(query, expected):
    assert canonical_query(query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("?b=2&a=x?y", "a=x%3Fy&b=2"),
        ("??a=1", "%3Fa=1"),
        ("?", ""),
    ],
)
def test_only_one_leading_question_mark_is_removed(query, expected):
    assert canonical_query(query) == expected


@pytest.mark.parametrize(
    "query",
    [
        "a=%zz",
        "a=%4",
        "k%4=v",
        "?%zz=1",
    ],
)
def test_percent_without_two_hex_digits_is_malformed(query):
    with pytest.raises(ValueError):
        canonical_query(query)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("+k+=%20v ", "k=v"),
        ("a=+", "a="),
        ("a=1&+b=2&a=+1", "a=1&b=2"),
        ("a=%09x%09", "a=%09x%09"),
        ("a=+x%0A", "a=x%0A"),
        ("a=+%09+", "a=%09"),
    ],
)
def test_only_space_bytes_are_trimmed(query, expected):
    assert canonical_query(query) == expected
