import sys

import pytest

sys.path.insert(0, "/app")
from wrapper import wrap_text  # noqa: E402

LOREM = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua ut enim ad minim veniam quis nostrud"
)
NBSP = "\u00a0"  # non-breaking space
NNBSP = "\u202f"  # narrow non-breaking space
FORM_FEED = "\x0c"
VERTICAL_TAB = "\x0b"
CARRIAGE_RETURN = "\r"


def test_greedy_fill():
    assert wrap_text("hello world", 20) == "hello world"
    assert wrap_text("the quick brown fox jumps over the lazy dog", 10) == (
        "the quick\nbrown fox\njumps over\nthe lazy\ndog"
    )


def test_line_may_be_exactly_width():
    assert wrap_text("aaaa bbbbb", 10) == "aaaa bbbbb"
    assert wrap_text("aaaa bbbbbb", 10) == "aaaa\nbbbbbb"


def test_input_lines_are_refilled_with_single_spaces():
    assert wrap_text("one\ntwo\nthree four", 20) == "one two three four"
    assert wrap_text("a   b \t c", 20) == "a b c"
    assert wrap_text("  lead and trail  \n\tnext  ", 40) == "lead and trail next"


def test_paragraphs_stay_separate():
    assert wrap_text("one two\nthree\n\nfour five six", 9) == "one two\nthree\n\nfour five\nsix"
    assert wrap_text("", 10) == ""


def test_plain_lines_within_width_and_words_kept():
    for width in (12, 33):
        lines = wrap_text(LOREM, width).split("\n")
        assert all(len(line) <= width for line in lines)
        assert " ".join(lines) == LOREM


def test_quote_lines_are_refilled_and_every_line_has_the_prefix():
    assert wrap_text("> one two\n> three", 40) == "> one two three"
    assert wrap_text(">   spaced \t out  ", 40) == "> spaced out"
    assert wrap_text("> aa bb cc dd", 7) == "> aa bb\n> cc dd"
    text = "> quoted words\n> go here\n\nplain words\ngo here"
    assert wrap_text(text, 40) == "> quoted words go here\n\nplain words go here"


# --- a word is never split -------------------------------------------------------------


def test_overlong_word_sits_alone_unsplit():
    url = "https://example.com/docs/wrapping"
    assert wrap_text(f"see {url} for details", 12) == f"see\n{url}\nfor details"
    assert wrap_text("abcdefghijklmnop qr st", 8) == "abcdefghijklmnop\nqr st"
    assert wrap_text("qr st abcdefghijklmnop", 8) == "qr st\nabcdefghijklmnop"
    assert wrap_text("it is a well-known fact", 14) == "it is a\nwell-known\nfact"
    # "abcdefghi" is 9 characters: with the quote prefix it cannot fit in 10.
    assert wrap_text("> ab abcdefghi cd", 10) == "> ab\n> abcdefghi\n> cd"


# --- the quote prefix counts toward the width -------------------------------------------


def test_quote_prefix_counts_toward_width():
    assert wrap_text("> 1234 678", 10) == "> 1234 678"
    assert wrap_text("> 1234 678", 9) == "> 1234\n> 678"


# --- a quote line starts with ">"; the space after it is not part of the marker ---------


def test_quote_line_needs_no_space_after_the_marker():
    assert wrap_text(">one two\n>   three", 40) == "> one two three"
    assert wrap_text(">tight", 40) == "> tight"


# --- a paragraph is a run of lines of one kind ------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [("> a b\nc d", "> a b\nc d"), ("a\n> b\n> c\nd", "a\n> b c\nd")],
)
def test_adjacent_quote_and_plain_lines_are_separate_paragraphs(text, expected):
    assert wrap_text(text, 40) == expected


# --- every blank line is kept -----------------------------------------------------------


def test_every_blank_line_is_kept():
    assert wrap_text("one\n\n\ntwo", 20) == "one\n\n\ntwo"
    assert wrap_text("\none two\n", 20) == "\none two\n"
    assert wrap_text("\n\n> one\n\n\n\n> two\n\n", 20) == "\n\n> one\n\n\n\n> two\n\n"


def test_whitespace_only_line_is_blank():
    assert wrap_text("one\n  \ntwo\n\t\nthree", 20) == "one\n\ntwo\n\nthree"


# --- whitespace is the space and the tab only; any other character is part of a word ----


@pytest.mark.parametrize(
    ("text", "width", "expected"),
    [
        (f"10{NBSP}km is far", 20, f"10{NBSP}km is far"),
        # "bb", the non-breaking space and "cc" are one word of 5 characters: it does not
        # fit after "aa" in 7.
        (f"aa bb{NBSP}cc dd", 7, f"aa\nbb{NBSP}cc\ndd"),
        (f"Qui{NNBSP}? Moi{NNBSP}!", 6, f"Qui{NNBSP}?\nMoi{NNBSP}!"),
        (f"> tel{NBSP}555 0100", 9, f"> tel{NBSP}555\n> 0100"),
        (f"a{VERTICAL_TAB}b c{CARRIAGE_RETURN}d", 20, f"a{VERTICAL_TAB}b c{CARRIAGE_RETURN}d"),
    ],
    ids=["nbsp-kept", "nbsp-word-length", "narrow-nbsp", "nbsp-in-quote", "other-controls"],
)
def test_only_space_and_tab_separate_words(text, width, expected):
    assert wrap_text(text, width) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A line holding only a form feed is a plain line with one word, not a blank line.
        (f"one\n\n{FORM_FEED}\n\ntwo", f"one\n\n{FORM_FEED}\n\ntwo"),
        (f"one\n{NBSP}\ntwo", f"one {NBSP} two"),
        (f"one\n{VERTICAL_TAB}\ntwo", f"one {VERTICAL_TAB} two"),
    ],
    ids=["form-feed-line", "nbsp-line", "vertical-tab-line"],
)
def test_only_space_and_tab_make_a_line_blank(text, expected):
    assert wrap_text(text, 20) == expected


# --- a plain output line whose first word starts with ">" gets one space in front -------


@pytest.mark.parametrize(
    ("text", "width", "expected"),
    [
        ("a >b >c", 3, "a\n >b\n >c"),
        # The first character is not ">", so these are plain lines.
        (" > not a quote", 40, " > not a quote"),
        ("\t>x y", 40, " >x y"),
    ],
    ids=["after-wrapping", "space-then-marker", "tab-then-marker"],
)
def test_plain_line_whose_first_word_starts_with_the_marker(text, width, expected):
    assert wrap_text(text, width) == expected


@pytest.mark.parametrize(
    ("text", "width", "expected"),
    [
        # " >bb cc" would be 7 characters.
        ("aaaa >bb cc", 6, "aaaa\n >bb\ncc"),
        # " >bc" is exactly 4 characters.
        ("zzzz >bc d", 4, "zzzz\n >bc\nd"),
        ("aaaa\n >bb\ncc", 6, "aaaa\n >bb\ncc"),
    ],
    ids=["one-too-long", "exactly-width", "already-wrapped"],
)
def test_the_space_in_front_counts_toward_width(text, width, expected):
    assert wrap_text(text, width) == expected


def test_word_starting_with_the_marker_inside_a_line_is_unchanged():
    # Only the first word of an output line matters, and only that line pays for the space.
    assert wrap_text("x >bb", 5) == "x >bb"
    assert wrap_text("so x > y holds", 40) == "so x > y holds"


def test_overlong_word_starting_with_the_marker_sits_alone():
    assert wrap_text("ab >abcdef cd", 5) == "ab\n >abcdef\ncd"


def test_quote_paragraph_gets_only_the_quote_prefix():
    assert wrap_text(">> nested reply", 40) == "> > nested reply"
    assert wrap_text("> aa >b", 5) == "> aa\n> >b"
