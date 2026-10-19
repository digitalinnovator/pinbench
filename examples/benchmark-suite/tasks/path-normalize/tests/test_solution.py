import sys

import pytest

sys.path.insert(0, "/app")
from pathnorm import is_within, normalize  # noqa: E402


@pytest.mark.parametrize("path", [".../.git/a-b/..c", "Docs_2/v1.0-rc"])
def test_already_normal(path):
    assert normalize(path) == path


def test_slash_runs():
    assert normalize("//a//b/") == "/a/b/"


@pytest.mark.parametrize(
    ("path", "expected"),
    [("/../../a", "/a"), ("a/../../../b", "../../b")],
)
def test_dotdot_with_no_name_to_cancel(path, expected):
    assert normalize(path) == expected


@pytest.mark.parametrize(("path", "expected"), [("", "."), ("/a/..", "/")])
def test_no_kept_segments(path, expected):
    assert normalize(path) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [("a/./b/.", "a/b/"), ("a/b/../..", "./"), ("..", "../")],
)
def test_last_segment_names_a_directory(path, expected):
    assert normalize(path) == expected


@pytest.mark.parametrize(
    "path",
    ["a b", "a/b\n", "café", "v٢/x", "a/-b", "a/b*/.."],
)
def test_normalize_rejects_an_invalid_path(path):
    with pytest.raises(ValueError):
        normalize(path)


@pytest.mark.parametrize(
    ("root", "path", "expected"),
    [
        ("/a/b", "/a/b", True),
        ("/a/b", "/a", False),
        ("/a/b", "/a/bc", False),
        ("/", "/a", True),
        (".", "a/b", True),
        ("a/..", "b", True),
    ],
)
def test_is_within_by_segments(root, path, expected):
    assert is_within(root, path) is expected


def test_is_within_absolute_against_relative():
    assert is_within("a", "/a/b") is False


@pytest.mark.parametrize(
    ("root", "path"),
    [
        ("..", "../a"),
        ("/", "/../a"),
        ("/a", "/a/../../a/b"),
        ("/../a", "/a/b"),
    ],
)
def test_is_within_with_a_dotdot_that_cancels_no_name(root, path):
    assert is_within(root, path) is False


@pytest.mark.parametrize(
    ("root", "path"),
    [("/a", "/a/b c"), ("/a", "b c"), ("..", "a b")],
)
def test_is_within_rejects_an_invalid_argument(root, path):
    with pytest.raises(ValueError):
        is_within(root, path)
