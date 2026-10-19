import sys
from decimal import Decimal

import pytest

sys.path.insert(0, "/app")
from invoice import Line, invoice_totals, line_total, tax_by_rate  # noqa: E402
from tax import line_tax  # noqa: E402


def has_two_places(value):
    return isinstance(value, Decimal) and value.as_tuple().exponent == -2


@pytest.mark.parametrize(
    ("amount", "rate", "tax"),
    [
        ("100.00", "0.20", "20.00"),
        ("19.99", "0.0825", "1.65"),
        ("0.01", "0.20", "0.00"),
        ("80.00", "0", "0.00"),
    ],
)
def test_line_tax(amount, rate, tax):
    assert line_tax(amount, rate) == Decimal(tax)


def test_line_tax_accepts_a_decimal_amount():
    assert line_tax(Decimal("14.97"), "0.0825") == Decimal("1.24")


@pytest.mark.parametrize(
    ("amount", "rate", "tax"), [("45.50", "0.05", "2.28"), ("21.50", "0.05", "1.08")]
)
def test_line_tax_is_not_computed_in_binary_floats(amount, rate, tax):
    assert line_tax(amount, rate) == Decimal(tax)


# Rule: line_tax returns amount times rate, "rounded half up to the cent".
@pytest.mark.parametrize(
    ("amount", "rate", "tax"), [("2.50", "0.05", "0.13"), ("20.10", "0.05", "1.01")]
)
def test_line_tax_rounds_half_a_cent_up(amount, rate, tax):
    assert line_tax(amount, rate) == Decimal(tax)


@pytest.mark.parametrize(
    ("quantity", "unit_price", "total"),
    [(3, "19.99", "59.97"), (0, "5.00", "0.00"), (7, "4.5", "31.50")],
)
def test_line_total(quantity, unit_price, total):
    assert line_total(Line("item", quantity, unit_price, "0.20")) == Decimal(total)


# Rule: every amount line_total returns is "a decimal.Decimal with exactly two decimal places";
# a unit_price has "at most two decimal places".
def test_line_total_has_two_decimal_places():
    assert has_two_places(line_total(Line("item", 7, "4.5", "0.20")))
    assert has_two_places(line_total(Line("item", 3, "10", "0.20")))


def test_amounts_are_decimals():
    lines = [Line("Widget", 3, "19.99", "0.20"), Line("Book", 2, "12.50", "0.05")]
    amounts = [line_tax("59.97", "0.20"), line_total(lines[0])]
    amounts += list(tax_by_rate(lines).values()) + list(invoice_totals(lines).values())
    assert all(isinstance(amount, Decimal) for amount in amounts)


MIXED = [
    Line("Widget", 3, "19.99", "0.20"),
    Line("Book", 2, "12.50", "0.05"),
    Line("Postage", 1, "4.95", "0"),
]


def test_tax_by_rate_with_one_line_per_rate():
    expected = {"0.20": Decimal("11.99"), "0.05": Decimal("1.25"), "0": Decimal("0.00")}
    assert tax_by_rate(MIXED) == expected


def test_tax_by_rate_taxes_a_line_on_its_line_total():
    assert tax_by_rate([Line("Filter", 3, "4.99", "0.0825")]) == {"0.0825": Decimal("1.24")}


def test_tax_by_rate_of_no_lines():
    assert tax_by_rate([]) == {}


# Rules: "The tax on a line is line_tax of its line total and its rate" and tax_by_rate maps a
# rate to "the sum of the taxes on the lines with that rate".
def test_tax_by_rate_sums_the_taxes_on_the_lines():
    lines = [Line(name, 1, "4.99", "0.0825") for name in ("Filter", "Gasket", "Seal")]
    assert tax_by_rate(lines) == {"0.0825": Decimal("1.23")}


# Rule: "Rates that are numerically equal are one rate, keyed by the tax_rate string of the
# first line that has it."
@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        (("10.00", "0.2"), ("5.50", "0.20"), {"0.2": Decimal("3.10")}),
        (("20.00", "0.050"), ("40.00", "0.05"), {"0.050": Decimal("3.00")}),
    ],
)
def test_tax_by_rate_merges_numerically_equal_rates(first, second, expected):
    lines = [Line("First", 1, *first), Line("Second", 1, *second)]
    assert tax_by_rate(lines) == expected


def test_invoice_totals_single_line():
    expected = {"net": Decimal("45.50"), "tax": Decimal("2.28"), "gross": Decimal("47.78")}
    assert invoice_totals([Line("Workshop seat", 1, "45.50", "0.05")]) == expected


def test_invoice_totals_mixed_rates():
    expected = {"net": Decimal("89.92"), "tax": Decimal("13.24"), "gross": Decimal("103.16")}
    assert invoice_totals(MIXED) == expected


def test_invoice_totals_two_lines_at_one_rate():
    lines = [Line("Setup", 1, "10.00", "0.20"), Line("Cable", 1, "5.50", "0.20")]
    expected = {"net": Decimal("15.50"), "tax": Decimal("3.10"), "gross": Decimal("18.60")}
    assert invoice_totals(lines) == expected


# Rules: invoice "tax" is "the sum of the tax_by_rate amounts", and each of those is "the sum
# of the taxes on the lines with that rate", every line's tax being rounded by line_tax.
def test_invoice_totals_sum_the_taxes_on_the_lines():
    lines = [
        Line("Ink", 1, "18.85", "0.0825"),
        Line("Toner", 1, "18.85", "0.0825"),
        Line("Paper", 2, "10.00", "0.20"),
    ]
    expected = {"net": Decimal("57.70"), "tax": Decimal("7.12"), "gross": Decimal("64.82")}
    assert invoice_totals(lines) == expected


# Rules: every `lines` argument "may be empty", and every amount invoice_totals returns is "a
# decimal.Decimal with exactly two decimal places".
def test_invoice_totals_of_no_lines():
    totals = invoice_totals([])
    assert set(totals) == {"net", "tax", "gross"}
    assert all(amount == 0 for amount in totals.values())
    assert all(has_two_places(amount) for amount in totals.values())
