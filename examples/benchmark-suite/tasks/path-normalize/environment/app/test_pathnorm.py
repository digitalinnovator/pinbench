from pathnorm import is_within, normalize


def test_pathnorm():
    assert normalize("/usr//local/./bin/../lib") == "/usr/local/lib"
    assert normalize("docs/a/../b") == "docs/b"
    assert is_within("/usr", "/usr/local") is True
