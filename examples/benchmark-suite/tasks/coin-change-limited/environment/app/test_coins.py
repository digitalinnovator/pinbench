from coins import make_change, pay_out


def test_uses_available_coins():
    assert make_change(40, {25: 1, 10: 2, 5: 3}) == {25: 1, 10: 1, 5: 1}


def test_pay_out_takes_the_coins_out_of_the_inventory():
    inventory = {25: 1, 10: 2, 5: 3}
    assert pay_out([40, 5], inventory) == [{25: 1, 10: 1, 5: 1}, {5: 1}]
    assert inventory == {25: 0, 10: 1, 5: 1}
