from money import charge, parse_ratio, split_amount


def test_weighted_split():
    assert split_amount(90, [2, 1]) == [60, 30]


def test_split_by_a_ratio_string():
    assert split_amount(100, parse_ratio("1:1")) == [50, 50]


def test_charge():
    balances = {"ann": 0, "bob": 5}
    charge(balances, 90, {"ann": 2, "bob": 1})
    assert balances == {"ann": 60, "bob": 35}
