import ast
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, "/app")
import invoices  # noqa: E402
import statements  # noqa: E402


def _invoice(label: str, money: str) -> str:
    return label.ljust(24) + money.rjust(16)


def _row(money: str) -> str:
    return "2026-03-01  " + "Card payment".ljust(20) + money.rjust(14)


def _statement_row(value) -> str:
    return statements.statement_row("2026-03-01", "Card payment", value)


# --- structure -------------------------------------------------------------------------


def test_private_helpers_deleted():
    assert not hasattr(invoices, "_money")
    assert not hasattr(statements, "_fmt_amount")


@pytest.mark.parametrize("module", [invoices, statements])
def test_module_imports_and_uses_shared_function(module):
    import money

    assert callable(money.format_money)
    tree = ast.parse(Path(module.__file__).read_text())
    local_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "money" and node.level == 0
        for alias in node.names
        if alias.name == "format_money"
    }
    assert local_names, "expected `from money import format_money`"
    used = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    assert local_names & used


def test_parameter_names_kept():
    one = Decimal("1")
    assert invoices.invoice_line(description="Widget", amount=one) == _invoice("Widget", "$1.00")
    assert invoices.invoice_total(amounts=[one]) == _invoice("TOTAL", "$1.00")
    row = statements.statement_row(date="2026-03-01", memo="Card payment", value=one)
    assert row == _row("$1.00")
    assert statements.closing_balance(values=[one]) == "Closing balance: $1.00"


# --- Decimal amounts: output unchanged -------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "money"),
    [
        ("-999999999999.999999", "-$999,999,999,999.99"),
        ("-1234.5", "-$1,234.50"),
        ("19.999", "$19.99"),
        ("-0.004", "-$0.00"),
    ],
)
def test_invoice_line_unchanged(amount, money):
    assert invoices.invoice_line("Widget", Decimal(amount)) == _invoice("Widget", money)


@pytest.mark.parametrize(
    ("amounts", "money"),
    [
        (["19.99", "-5", "1000.01"], "$1,015.00"),
        (["-0.006", "-0.006"], "$0.00"),
    ],
)
def test_invoice_total_unchanged(amounts, money):
    assert invoices.invoice_total([Decimal(a) for a in amounts]) == _invoice("TOTAL", money)


@pytest.mark.parametrize(
    ("amount", "money"),
    [
        ("999999999999.985", "$999999999999.99"),
        ("-0.004", "$0.00"),
        ("-0.005", "($0.01)"),
    ],
)
def test_statement_row_unchanged(amount, money):
    assert _statement_row(Decimal(amount)) == _row(money)


def test_closing_balance_unchanged():
    values = [Decimal("100"), Decimal("-2500.752"), Decimal("-0.003")]
    assert statements.closing_balance(values) == "Closing balance: ($2400.76)"


# --- int and str amounts ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "money"),
    [(1250, "$1,250.00"), ("-2.349", "-$2.34"), ("-0.004", "-$0.00")],
)
def test_invoice_line_accepts_int_and_str(amount, money):
    assert invoices.invoice_line("Widget", amount) == _invoice("Widget", money)


@pytest.mark.parametrize(("amount", "money"), [(45, "$45.00"), ("-0.125", "($0.13)")])
def test_statement_row_accepts_int_and_str(amount, money):
    assert _statement_row(amount) == _row(money)


def test_invoice_total_accepts_a_mixed_list():
    amounts = ["10.006", 5, Decimal("5.006")]
    assert invoices.invoice_total(amounts) == _invoice("TOTAL", "$20.00")


def test_closing_balance_accepts_a_mixed_list():
    values = ["100", -2500, Decimal("-0.752"), "-0.003"]
    assert statements.closing_balance(values) == "Closing balance: ($2400.76)"


# --- str amounts that are not in the stated form ---------------------------------------

ARABIC_INDIC_TWO = "٢"  # a digit, but not one of 0-9


@pytest.mark.parametrize(
    "text",
    ["", "12.5 ", "12.5\n", "1e3", "1" + ARABIC_INDIC_TWO, "007", "-0", "-0.00"],
)
def test_other_str_amount_raises_value_error(text):
    with pytest.raises(ValueError):
        invoices.invoice_line("Widget", text)
    with pytest.raises(ValueError):
        _statement_row(text)


def test_other_str_amount_in_a_list_raises_value_error():
    with pytest.raises(ValueError):
        invoices.invoice_total([Decimal("1"), "1e3"])
    with pytest.raises(ValueError):
        statements.closing_balance(["5", "5 "])
    with pytest.raises(ValueError):
        invoices.invoice_total([7, "007"])
    with pytest.raises(ValueError):
        statements.closing_balance([Decimal("1"), "-0"])
