from splitter import split_toplevel


def test_commas_inside_brackets_do_not_split():
    assert split_toplevel("a, f(b, c), d") == ["a", "f(b, c)", "d"]


def test_unquote_removes_the_enclosing_quotes():
    assert split_toplevel("'a, b', c", unquote=True) == ["a, b", "c"]
