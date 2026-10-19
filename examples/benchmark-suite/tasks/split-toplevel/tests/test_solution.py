import sys

import pytest

sys.path.insert(0, "/app")
from splitter import split_toplevel  # noqa: E402


@pytest.mark.parametrize(
    ("text", "items"),
    [
        (
            "f(a, b), g[1, 2], (c, [d, {e, f}]), h",
            ["f(a, b)", "g[1, 2]", "(c, [d, {e, f}])", "h"],
        ),
        ("\"a, b\", 'c, d', e", ['"a, b"', "'c, d'", "e"]),
        ("  a  b ,\tc\n", ["a  b", "c\n"]),
        ("\n", ["\n"]),
        (" ,a,,b, ", ["", "a", "", "b", ""]),
        ('"it\'s, fine", f("]", x), ")"', ['"it\'s, fine"', 'f("]", x)', '")"']),
        (r"'it\'s, ok', b", [r"'it\'s, ok'", "b"]),
        (r"'a\\', b", [r"'a\\'", "b"]),
        (r"a\, b", ["a\\", "b"]),
        (r"a\'b, c', d", [r"a\'b, c'", "d"]),
        # A quote character directly after an ASCII letter or digit is an ordinary character.
        ("it's, f(don't, x), 6'2\", 5'11\"", ["it's", "f(don't, x)", "6'2\"", "5'11\""]),
        # ... and after any other character it starts a quoted string.
        ("\u00e9'a, b', c", ["\u00e9'a, b'", "c"]),
        ("_'a, b', c", ["_'a, b'", "c"]),
    ],
)
def test_split(text, items):
    assert split_toplevel(text) == items


@pytest.mark.parametrize(("text", "unquote"), [("", False), (" \t ", False), ("\t  ", True)])
def test_blank_text_has_no_items(text, unquote):
    assert split_toplevel(text, unquote=unquote) == []


@pytest.mark.parametrize(
    "text",
    [
        "(a, b",
        "a)",
        "([a)]",
        "a, 'b, c",
        r"'a\'",
        "'abc\\",
    ],
)
def test_invalid(text):
    for unquote in (False, True):
        with pytest.raises(ValueError):
            split_toplevel(text, unquote=unquote)


@pytest.mark.parametrize(
    ("text", "items"),
    [
        ("'a, b', \"c\", d", ["a, b", "c", "d"]),
        # An item is trimmed first, so the spaces and tabs inside a quoted string stay.
        ("' a ', \"\", x", [" a ", "", "x"]),
        ("  ' a' b ' c '  ,\tx '\t'", [" a b  c ", "x \t"]),
        # The backslash of each escape goes, the escaped character stays as it is.
        (
            "'it\\'s', \"a\\\\b\", 'x\\ny', 'p\\\nq'",
            ["it's", "a\\b", "xny", "p\nq"],
        ),
        # Every quoted string that starts while no bracket is open is replaced.
        ("'a' + \"b\", 'p''q', x 'y' z", ["a + b", "pq", "x y z"]),
        # A quoted string that starts inside a bracket is left alone.
        (
            r"""f('a, b', "c"), [' x '], 'g'('it\'s')""",
            ["f('a, b', \"c\")", "[' x ']", r"g('it\'s')"],
        ),
        # A quote character directly after an ASCII letter or digit is no quoted string.
        (r"it's, don't 'go', 'a'b'c', a\, 6'", ["it's", "don't go", "ab'c'", "a\\", "6'"]),
        ("\u00e9'a, b', c", ["\u00e9a, b", "c"]),
    ],
)
def test_unquote(text, items):
    assert split_toplevel(text, unquote=True) == items
