import sys

import pytest

sys.path.insert(0, "/app")
from confstrip import strip_comments  # noqa: E402

CASES = [
    # Line comments, block comments on one line, and text that must not change.
    pytest.param("", "", id="empty"),
    pytest.param("a = 1 # one\n", "a = 1 \n", id="line-comment-keeps-space-before-it"),
    pytest.param("x = 1 # no newline at the end", "x = 1 ", id="line-comment-at-end-of-input"),
    pytest.param("a/* x */b /* y */c\n", "ab c\n", id="two-block-comments-on-one-line"),
    pytest.param("r = 4 / 2 * 3 /", "r = 4 / 2 * 3 /", id="slash-and-star-alone-slash-at-end"),
    # Strings are kept; comment markers inside them are text.
    pytest.param('url = "http://x/#top"\n', 'url = "http://x/#top"\n', id="hash-in-string"),
    pytest.param('a = "/* no */" /* yes */\n', 'a = "/* no */" \n', id="block-in-string"),
    # In a double-quoted string a backslash escapes the next character.
    pytest.param(
        r'say = "a \"quoted\" # word" # c' + "\n",
        r'say = "a \"quoted\" # word" ' + "\n",
        id="escaped-quote",
    ),
    pytest.param(r'dir = "C:\\" # win' + "\n", r'dir = "C:\\" ' + "\n", id="escaped-backslash"),
    # Single-quoted strings: no escapes, and the other quote character is text.
    pytest.param("t = '#tag /* x' # c\n", "t = '#tag /* x' \n", id="markers-in-single-quoted"),
    pytest.param(
        r"p = 'C:\dir\' # win" + "\n", r"p = 'C:\dir\' " + "\n", id="backslash-in-single-quoted"
    ),
    pytest.param("m = 'say \"hi' # c\n", "m = 'say \"hi' \n", id="double-quote-in-single-quoted"),
    pytest.param('m = "it\'s" # c\n', 'm = "it\'s" \n', id="apostrophe-in-double-quoted"),
    # Block comments across lines keep their newlines.
    pytest.param("a = 1 /* one\ntwo */ b = 2\n", "a = 1 \n b = 2\n", id="block-over-two-lines"),
    pytest.param(
        "/*\n * header\n *\n */\nname = 1\n", "\n\n\n\nname = 1\n", id="block-over-four-lines"
    ),
    pytest.param("a = 1 /* open\nb = 2\n", "a = 1 \n\n", id="unclosed-block-over-lines"),
    pytest.param("x /*/ y */ z\n", "x  z\n", id="close-must-follow-the-opening-marker"),
    pytest.param("/* a /* b */ c */\n", " c */\n", id="no-nesting"),
    # Inside a comment, quotes and comment markers mean nothing.
    pytest.param("# it's \"open\nx = 1 # y\n", "\nx = 1 \n", id="quotes-in-line-comment"),
    pytest.param("# /* not a block\ny = 2\n# */\n", "\ny = 2\n\n", id="block-open-in-line-comment"),
    pytest.param('/* # " */ z = "v" # w\n', ' z = "v" \n', id="hash-and-quote-in-block"),
    # A string never spans lines: a newline, escaped or not, ends it.
    pytest.param('a = "b # c\nd = 1 # e\n', 'a = "b # c\nd = 1 \n', id="unclosed-string"),
    pytest.param("a = 'b # c\nd = 1 # e\n", "a = 'b # c\nd = 1 \n", id="unclosed-single-quoted"),
    pytest.param(
        'a = "x\\\nb = 1 # c\n', 'a = "x\\\nb = 1 \n', id="backslash-before-newline-in-string"
    ),
    # Every input has a result.
    pytest.param('a = "x\\', 'a = "x\\', id="input-ends-with-backslash-in-open-string"),
]


@pytest.mark.parametrize(("source", "expected"), CASES)
def test_strip_comments(source, expected):
    assert strip_comments(source) == expected
