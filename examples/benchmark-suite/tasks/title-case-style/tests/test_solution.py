import sys

import pytest

sys.path.insert(0, "/app")
from headline import headline_case  # noqa: E402


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        ("of", "Of"),
        ("The Lord Of The Rings", "The Lord of the Rings"),
        ("of mice and, of course, men", "Of Mice and, of Course, Men"),
    ],
)
def test_small_words(text, expected):
    assert headline_case(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("how an OR gate works at eBay", "How an OR Gate Works at eBay"),
        ("life in a post-COVID world", "Life in a Post-COVID World"),
        ("state-of-the-art design", "State-Of-The-Art Design"),
        ("the a- and b-sides of a single", "The A- and B-Sides of a Single"),
    ],
)
def test_parts_and_existing_capitals(text, expected):
    assert headline_case(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('"the" is a word', '"The" Is a Word'),
        ("The Hobbit (Or There And Back Again)", "The Hobbit (or There and Back Again)"),
        ("the 2nd act of a 10th-century play", "The 2nd Act of a 10th-Century Play"),
    ],
)
def test_lead_of_a_part(text, expected):
    assert headline_case(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("   ", "   "),
        ("  the end", "  The End"),
        ("what is it for ", "What Is It For "),
        ("rust:  the good parts", "Rust:  The Good Parts"),
    ],
)
def test_spaces_are_kept(text, expected):
    assert headline_case(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# the lord of the rings", "# The Lord of the Rings"),
        ("what is it for ?", "What Is It For ?"),
        ("## a guide to ##", "## A Guide To ##"),
        ("rust : the good parts", "Rust : The Good Parts"),
    ],
)
def test_runs_that_are_not_words(text, expected):
    assert headline_case(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("what it is for: a guide", "What It Is for: A Guide"),
        ("stop! in the name of love", "Stop! In the Name of Love"),
        ('"who is it for?" a guide to the law', '"Who Is It for?" A Guide to the Law'),
        ("(part one:) the end of it", "(Part One:) The End of It"),
        ("**note:** the end of an era", "**Note:** The End of an Era"),
        ("at 10:30 the show starts", "At 10:30 the Show Starts"),
        ("what now? - the sequel to it all", "What Now? - The Sequel to It All"),
    ],
)
def test_clauses(text, expected):
    assert headline_case(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("the lord of\nthe rings", "The Lord Of\nThe Rings"),
        ("war and peace\n", "War and Peace\n"),
        ("- of mice and men\n\n- the end\n", "- Of Mice and Men\n\n- The End\n"),
        ("what is it for\r\nthe end\r\n", "What Is It For\r\nThe End\r\n"),
    ],
)
def test_lines(text, expected):
    assert headline_case(text) == expected
