from timerange import parse_range


def test_working_day():
    assert parse_range("9am-5:30pm") == (540, 510)
