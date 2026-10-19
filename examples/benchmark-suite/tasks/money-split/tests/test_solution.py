import sys

import pytest

sys.path.insert(0, "/app")
from money import charge, parse_ratio, split_amount  # noqa: E402


def test_largest_remainder():
    assert split_amount(5, [7]) == [5]
    assert split_amount(0, [3, 1]) == [0, 0]
    assert split_amount(100, [3, 2, 1]) == [50, 33, 17]
    assert split_amount(7, [5, 3, 2]) == [4, 2, 1]


def test_equal_fractional_parts_and_equal_weights_earlier_party_first():
    assert split_amount(2, [1, 1, 1]) == [1, 1, 0]
    assert split_amount(100, [1, 1, 1, 1, 1, 1, 1]) == [15, 15, 14, 14, 14, 14, 14]


def test_equal_fractional_parts_larger_weight_first():
    assert split_amount(2, [1, 3]) == [0, 2]
    assert split_amount(6, [1, 3]) == [1, 5]
    assert split_amount(9, [1, 1, 5, 5]) == [1, 0, 4, 4]


def test_zero_weight_gets_zero():
    assert split_amount(10, [1, 1, 1, 0]) == [4, 3, 3, 0]
    assert split_amount(5, [0, 3, 0, 3]) == [0, 3, 0, 2]


def test_parts_are_ints_that_sum_to_the_total():
    for weights in ([1, 1, 1], [3, 2, 1], [0, 7, 2, 2], [5, 1], [1, 1, 1, 1, 1, 1]):
        for total in range(60):
            parts = split_amount(total, list(weights))
            assert isinstance(parts, list)
            assert len(parts) == len(weights)
            assert all(type(part) is int for part in parts)
            assert sum(parts) == total


@pytest.mark.parametrize("weights", [[], [2, -1], [0, 0]], ids=["empty", "negative", "all zero"])
def test_invalid_weights(weights):
    for total in (100, 0, -100):
        with pytest.raises(ValueError):
            split_amount(total, list(weights))


def test_refund():
    assert split_amount(-100, [3, 2, 1]) == [-50, -33, -17]
    assert split_amount(-100, [1, 1, 1]) == [-34, -33, -33]
    assert split_amount(-2, [1, 3]) == [0, -2]


def test_refund_is_the_negative_of_the_charge():
    for weights in ([1, 1], [1, 1, 1], [3, 2, 1], [0, 5, 5], [2, 2, 2, 1]):
        for total in range(1, 40):
            charged = split_amount(total, list(weights))
            refunded = split_amount(-total, list(weights))
            assert refunded == [-part for part in charged]


def test_shares_are_exact_for_ints_of_any_size():
    assert split_amount(10**17 + 3, [1, 2]) == [33333333333333334, 66666666666666669]
    third = 33333333333333333333
    assert split_amount(10**20, [1, 1, 1]) == [third + 1, third, third]


def _generate(weights):
    yield from weights


def test_weights_can_be_any_iterable():
    for make in (iter, _generate, tuple):
        assert split_amount(10, make([1, 1, 1, 0])) == [4, 3, 3, 0]
        assert split_amount(7, make([5, 3, 2])) == [4, 2, 1]
        for total in (100, 0):
            with pytest.raises(ValueError):
                split_amount(total, make([]))


def test_parse_ratio():
    assert parse_ratio("3:2:1") == [3, 2, 1]
    assert parse_ratio("7") == [7]
    assert parse_ratio("0:10:205") == [0, 10, 205]
    assert parse_ratio("123456789012345678901234567890:1") == [123456789012345678901234567890, 1]
    assert split_amount(100, parse_ratio("3:2:1")) == [50, 33, 17]


def test_parse_ratio_allows_spaces_around_a_weight():
    assert parse_ratio("3 : 2 : 1") == [3, 2, 1]
    assert parse_ratio(" 3:2 ") == [3, 2]
    assert parse_ratio("10   :0") == [10, 0]
    assert parse_ratio("  7  ") == [7]


@pytest.mark.parametrize(
    "texts",
    [
        ["3\t:2", "3:\t2", "\t3:2", "3:2\t"],
        ["3:2\n", "\n3:2", "3\n:2", "3:2\r\n"],
        ["+3:2", "3:+2", "-3:2", "3:-2"],
        ["3_0:2", "3:1_000"],
        ["03:2", "3:00", "007", "3: 02 :1"],
        ["", " ", ":", "3::2", ":3", "3:", "3: :2"],
        ["a:b", "3.0:2", "3;2", "1e2:1", "0x10:1", "3,2", "1 0:2"],
        # Digits that are not ASCII 0-9: Arabic-Indic three and zero, fullwidth two and zero.
        ["٣:2", "3:２", "1٠:2", "3:2０"],
    ],
    ids=[
        "tab",
        "newline",
        "sign",
        "underscore",
        "leading zero",
        "empty weight",
        "not a weight",
        "digit outside 0-9",
    ],
)
def test_parse_ratio_rejects_any_other_string(texts):
    for text in texts:
        with pytest.raises(ValueError):
            parse_ratio(text)


def test_charge_adds_each_part_to_the_balance():
    balances = {"ann": 100, "bob": 0, "cy": -30, "dee": 7}
    charge(balances, 10, {"ann": 1, "bob": 1, "cy": 1})
    assert balances == {"ann": 104, "bob": 3, "cy": -27, "dee": 7}
    charge(balances, -100, {"cy": 3, "ann": 2, "bob": 1, "dee": 0})
    assert balances == {"ann": 71, "bob": -14, "cy": -77, "dee": 7}


def test_charge_splits_in_the_order_of_weights():
    balances = {"ann": 0, "bob": 0, "cy": 0}
    charge(balances, 2, {"cy": 1, "ann": 1, "bob": 1})
    assert balances == {"ann": 1, "bob": 0, "cy": 1}
    charge(balances, 2, {"ann": 1, "bob": 3})
    assert balances == {"ann": 1, "bob": 2, "cy": 1}


def test_charge_with_invalid_weights_changes_nothing():
    for weights in ({}, {"ann": 0, "bob": 0}, {"ann": 2, "bob": -1}):
        balances = {"ann": 10, "bob": 20}
        with pytest.raises(ValueError):
            charge(balances, 100, weights)
        assert balances == {"ann": 10, "bob": 20}


@pytest.mark.parametrize(
    "cases",
    [
        [{"zed": 0, "ann": 0}, {"ann": 0, "zed": 0}],
        [{"zed": 2, "ann": -1}, {"ann": -1, "zed": 2}, {"ann": 2, "zed": -1}],
    ],
    ids=["all zero", "negative"],
)
def test_charge_with_invalid_weights_and_a_missing_party_raises_value_error(cases):
    for weights in cases:
        balances = {"ann": 10, "bob": 20}
        with pytest.raises(ValueError):
            charge(balances, 100, weights)
        assert balances == {"ann": 10, "bob": 20}


@pytest.mark.parametrize(
    "weights",
    [
        {"zed": 1, "ann": 1, "bob": 1},
        {"ann": 1, "zed": 1, "bob": 1},
        {"ann": 1, "bob": 1, "zed": 1},
    ],
    ids=["missing first", "missing middle", "missing last"],
)
def test_charge_with_a_missing_party_changes_nothing(weights):
    balances = {"ann": 10, "bob": 20}
    with pytest.raises(KeyError):
        charge(balances, 100, weights)
    assert balances == {"ann": 10, "bob": 20}
