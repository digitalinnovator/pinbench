import sys

import pytest

sys.path.insert(0, "/app")
from text import slugify  # noqa: E402


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Hello World", "hello-world"),
        ("  Crème Brûlée!  ", "creme-brulee"),
        ("Über   cool -- stuff", "uber-cool-stuff"),
        ("C++ & Rust: 2026 edition", "c-rust-2026-edition"),
        ("日本語", "n-a"),
        ("---", "n-a"),
        ("", "n-a"),
    ],
)
def test_examples(title, slug):
    assert slugify(title) == slug


def test_length_cut_at_hyphen():
    title = "word " * 30
    slug = slugify(title)
    assert len(slug) <= 60
    assert not slug.endswith("-")
    assert slug == "-".join(["word"] * 12)


def test_length_hard_cut_without_hyphen():
    slug = slugify("a" * 100)
    assert slug == "a" * 60
