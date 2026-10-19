from sizes import format_size, parse_size


def test_examples():
    assert format_size(500) == "500 B"
    assert format_size(1536) == "1.5 KiB"
    assert parse_size("1.5 KiB") == 1536
