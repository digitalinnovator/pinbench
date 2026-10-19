from decimal import Decimal

from invoices import invoice_line
from statements import statement_row


def test_invoice_line():
    assert invoice_line("Consulting", Decimal("1250.00")).endswith(" $1,250.00")


def test_statement_row():
    assert statement_row("2026-03-01", "Refund", Decimal("-20.00")).endswith(" ($20.00)")
