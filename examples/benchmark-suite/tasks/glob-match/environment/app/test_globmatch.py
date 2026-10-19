from globmatch import glob_match


def test_basic():
    assert glob_match("src/*.py", "src/main.py") is True
    assert glob_match("src/*.py", "src/main.txt") is False
    assert glob_match("docs/**/*.md", "docs/guide/intro.md") is True
