from wrapper import wrap_text


def test_wraps_a_paragraph():
    assert wrap_text("the quick brown fox jumps over the lazy dog", 15) == (
        "the quick brown\nfox jumps over\nthe lazy dog"
    )


def test_quote_keeps_its_prefix():
    assert wrap_text("> hello there", 40) == "> hello there"
