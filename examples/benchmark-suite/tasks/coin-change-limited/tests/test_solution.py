import sys

import pytest

sys.path.insert(0, "/app")
from coins import make_change, pay_out  # noqa: E402


@pytest.mark.parametrize(
    ("amount", "inventory", "expected"),
    [
        (63, {25: 2, 10: 3, 5: 2, 1: 4}, {25: 2, 10: 1, 1: 3}),
        (5, {5: 0, 1: 5}, {1: 5}),
        (0, {}, {}),
        # Fewest coins: two 3s beat 4 + 1 + 1.
        (6, {4: 2, 3: 2, 1: 5}, {3: 2}),
    ],
)
def test_exact_amount_with_fewest_coins(amount, inventory, expected):
    assert make_change(amount, inventory) == expected


@pytest.mark.parametrize(("amount", "inventory"), [(7, {2: 5}), (11, {5: 1, 1: 3})])
def test_impossible(amount, inventory):
    assert make_change(amount, inventory) is None


@pytest.mark.parametrize(
    ("amount", "inventory", "expected"),
    [
        (8, {5: 1, 4: 2, 3: 1}, {4: 2}),  # not 5 + 3
        (16, {7: 1, 5: 3, 2: 2, 1: 1}, {5: 3, 1: 1}),  # not 7 + 5 + 2 + 2
        (18, {2: 2, 7: 2, 1: 1, 5: 2}, {7: 2, 2: 2}),  # not 7 + 5 + 5 + 1
    ],
)
def test_fewer_denominations_among_fewest_coins(amount, inventory, expected):
    assert make_change(amount, inventory) == expected


@pytest.mark.parametrize(
    ("amount", "inventory", "expected"),
    [
        (21, {15: 2, 8: 2, 5: 1, 3: 2, 1: 3}, {15: 1, 3: 2}),  # not 15+5+1, not 8+8+5
        # Three coins each: 10+7+1 has three denominations; 10+4+4 beats 7+7+4 on the 10, which
        # is the largest denomination although the inventory does not list it first.
        (18, {7: 2, 1: 2, 10: 1, 4: 3}, {10: 1, 4: 2}),
        # Four coins, three denominations and one 10 each: 10+7+7+3 beats 10+7+5+5 on the 7s.
        (27, {5: 2, 3: 2, 10: 1, 7: 2}, {10: 1, 7: 2, 3: 1}),
    ],
)
def test_largest_denomination_first_when_still_tied(amount, inventory, expected):
    assert make_change(amount, inventory) == expected


def test_inventory_is_not_modified():
    inventory = {5: 2, 2: 3, 1: 1}
    make_change(9, inventory, reserve=1)
    assert inventory == {5: 2, 2: 3, 1: 1}


@pytest.mark.parametrize(
    ("amount", "inventory", "expected"),
    [
        (40, {5: 3, 25: 1, 10: 2}, [(5, 1), (25, 1), (10, 1)]),
        (17, {1: 3, 10: 1, 2: 1, 5: 1}, [(10, 1), (2, 1), (5, 1)]),
    ],
)
def test_result_keys_follow_the_inventory_order(amount, inventory, expected):
    assert list(make_change(amount, inventory).items()) == expected


@pytest.mark.parametrize(
    ("amount", "inventory", "reserve", "expected"),
    [
        (20, {10: 3, 5: 4}, 2, {10: 1, 5: 2}),  # only one 10 is above the reserve
        (15, {10: 2, 5: 5}, 2, {5: 3}),  # the 10s are exactly the reserve
        (10, {10: 1, 5: 2}, 1, None),  # one 5 is all that may be used
        # A denomination that holds fewer coins than the reserve is not used; the others are.
        (15, {10: 1, 5: 5}, 2, {5: 3}),
        (6, {5: 0, 2: 4, 1: 3}, 1, {2: 3}),
    ],
)
def test_reserve_is_held_back(amount, inventory, reserve, expected):
    assert make_change(amount, inventory, reserve) == expected


@pytest.mark.parametrize(
    ("amounts", "inventory", "reserve", "expected", "left"),
    [
        ([], {5: 1}, 0, [], {5: 1}),
        # The third 10 has to come from the 5s, because the first two took both 10s.
        ([10, 0, 10, 10], {10: 2, 5: 3}, 0, [{10: 1}, {}, {10: 1}, {5: 2}], {10: 0, 5: 1}),
        ([15, 12], {10: 2, 5: 3, 1: 4}, 0, [{10: 1, 5: 1}, {10: 1, 1: 2}], {10: 0, 5: 2, 1: 2}),
        ([10, 10, 10], {10: 3, 5: 4}, 1, [{10: 1}, {10: 1}, {5: 2}], {10: 1, 5: 2}),
    ],
)
def test_pay_out_draws_each_amount_from_what_is_left(amounts, inventory, reserve, expected, left):
    assert pay_out(amounts, inventory, reserve) == expected
    assert inventory == left


def test_pay_out_results_follow_the_inventory_order():
    results = pay_out([16, 11], {1: 4, 5: 3, 10: 2})
    assert [list(result.items()) for result in results] == [
        [(1, 1), (5, 1), (10, 1)],
        [(1, 1), (10, 1)],
    ]


@pytest.mark.parametrize(
    ("amounts", "inventory", "reserve"),
    [
        ([10, 10, 10], {10: 2, 5: 1}, 0),  # the third payout fails
        ([7, 6, 2], {5: 1, 2: 3}, 0),  # 6 fails once 7 has taken a 2
        # Both 5s that may be used are gone after the second payout; the 10 left is held back.
        ([10, 10, 10], {10: 2, 5: 3}, 1),
    ],
)
def test_pay_out_that_fails_changes_nothing(amounts, inventory, reserve):
    before = dict(inventory)
    assert pay_out(amounts, inventory, reserve) is None
    assert inventory == before
