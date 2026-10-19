import re
import sys

import pytest

sys.path.insert(0, "/app")
from envfile import parse_env  # noqa: E402

VALID = {
    "skipped_lines_and_duplicates": (
        "# top\n\nA=x\n  # indented\n\t\nB_2=y\nA=z\n",
        {"A": "z", "B_2": "y"},
    ),
    "line_blanks_and_export": (
        "  A=x  \n\tB=y\t\nexport C=z\nexport   _d=w\nexport\tE=v",
        {"A": "x", "B": "y", "C": "z", "_d": "w", "E": "v"},
    ),
    "unquoted_trimmed_and_empty": (
        "A=  hello world  \nB=b=c==\nC=\nD=x",
        {"A": "hello world", "B": "b=c==", "C": "", "D": "x"},
    ),
    "quotes_keep_padding": (
        "A='hello world'\nB=\"  padded  \"\nC= 'x'\nD=''\nE=\"\"",
        {"A": "hello world", "B": "  padded  ", "C": "x", "D": "", "E": ""},
    ),
    "double_quoted_escapes": (
        r'A="one\ntwo\tthree"' + "\n" + r'B="say \"hi\""' + "\n" + r'C="C:\\dir"',
        {"A": "one\ntwo\tthree", "B": 'say "hi"', "C": "C:\\dir"},
    ),
    "double_other_backslash_kept": (r'A="100\% sure"', {"A": "100\\% sure"}),
    # Escapes are read left to right: an escaped backslash does not escape what follows it.
    "escaped_backslash_then_n": (r'A="a\\nb"', {"A": "a\\nb"}),
    "escaped_backslash_before_closing_quote": (
        r'A="C:\\"' + "\n" + r'B="C:\\" # c',
        {"A": "C:\\", "B": "C:\\"},
    ),
    "comment_after_value": (
        "A=x # note\nB=hello world\t# note\nC=\"x\" # note\nD='y'\t# note",
        {"A": "x", "B": "hello world", "C": "x", "D": "y"},
    ),
    "comment_right_after_equals": ("A= #x\nB=y", {"A": "", "B": "y"}),
    # A '#' is a comment only outside a quoted value and only directly after a blank.
    "hash_glued_to_unquoted": ("URL=http://host/page#top", {"URL": "http://host/page#top"}),
    "hash_right_after_equals": ("COLOR=#ff0000 # red", {"COLOR": "#ff0000"}),
    "hash_in_quotes": ("A=\"a # b\"\nB='a # b' # note", {"A": "a # b", "B": "a # b"}),
    "quote_inside_unquoted_then_comment": ('A=a"b # c', {"A": 'a"b'}),
    # Escapes are processed only in double-quoted values.
    "escapes_only_in_double_quotes": (
        r"A='one\ntwo'" + "\n" + r"B=one\ttwo",
        {"A": "one\\ntwo", "B": "one\\ttwo"},
    ),
    "single_quoted_ends_at_next_quote": (r"A='C:\dir\'", {"A": "C:\\dir\\"}),
    # A blank is a space or a tab: a form feed or a vertical tab is an ordinary character.
    "only_space_and_tab_are_blanks": (
        "A=x\x0c\nB=y\x0b# c",
        {"A": "x\x0c", "B": "y\x0b# c"},
    ),
}

# No malformed line contains a digit, so a message that echoes the line cannot pass by accident.
MALFORMED = {
    "no_equals": ("A=x\nB\n", 2),
    "invalid_key": ("\n# c\nA=x\nA-B=y", 4),
    "blank_before_equals": ("A=x\nB =y", 2),
    "double_quote_never_closed": ('A=x\n\nB="abc', 3),
    "escaped_quote_does_not_close": ("A=x\n" + r'B="a\"', 2),
    "single_quote_never_closed": ("A='abc\nB=x", 1),
    "text_after_closing_quote": ('# c\nA="x" y', 2),
    "hash_glued_to_closing_quote": ('A=x\nB="x"#c', 2),
}


@pytest.mark.parametrize(("text", "expected"), VALID.values(), ids=VALID.keys())
def test_valid(text, expected):
    assert parse_env(text) == expected


@pytest.mark.parametrize(("text", "line"), MALFORMED.values(), ids=MALFORMED.keys())
def test_malformed(text, line):
    with pytest.raises(ValueError) as info:
        parse_env(text)
    assert re.search(rf"(?<!\d){line}(?!\d)", str(info.value))
