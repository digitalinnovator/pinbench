import sys

import pytest

sys.path.insert(0, "/app")
from globmatch import glob_match  # noqa: E402


@pytest.mark.parametrize(
    ("pattern", "path"),
    [
        ("x**y", "xy"),
        ("file[0-9].lo?", "file9.log"),
        ("[^abc]at", "hat"),
        ("v1.0+(beta)", "v1.0+(beta)"),
        ("**/*.py", ".venv/lib/mod.py"),
        ("a/**/b", "a/b"),
        ("a/**", "a"),
        ("[]a]x", "]x"),
        ("[^]a]x", "bx"),
        ("[bz-a]x", "bx"),
    ],
)
def test_matches(pattern, path):
    assert glob_match(pattern, path) is True


@pytest.mark.parametrize(
    ("pattern", "path"),
    [
        ("*.txt", "dir/notes.txt"),
        ("[!abc]at", "bat"),
        ("a[!b]c", "a/c"),
        ("a/**/b", "a/x/y"),
        ("**.py", "src/mod.py"),
        ("[!]a]x", "]x"),
        ("[z-a]", "z"),
        ("readme.md", "README.md"),
    ],
)
def test_does_not_match(pattern, path):
    assert glob_match(pattern, path) is False


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        # Letters a-z and A-Z match in either case, as literals and as set members.
        ("Read*.MD", "README.md", True),
        ("[a-f]1", "D1", True),
        ("[BX]1", "b1", True),
        ("[!a-f]1", "D1", False),
        # Every other character is compared as before.
        ("é.txt", "É.txt", False),
        ("caf[éa]", "cafÉ", False),
    ],
)
def test_ignore_case(pattern, path, expected):
    assert glob_match(pattern, path, ignore_case=True) is expected


@pytest.mark.parametrize(
    ("pattern", "path"),
    [
        ("x[ab", "xa"),
        # Malformed whatever the path is.
        ("x[ab", "y"),
        ("a/[b", "x/y"),
        # The class must close in its own segment.
        ("[ab/c]", "a/c"),
        # A `]` in first place is a member, so nothing closes these classes.
        ("[]", "]"),
        ("[!]", "a"),
    ],
)
def test_malformed_pattern(pattern, path):
    with pytest.raises(ValueError):
        glob_match(pattern, path)
