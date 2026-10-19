from decimal import Decimal

from invoice import Line, invoice_totals


def test_reported_invoice():
    totals = invoice_totals([Line("Workshop seat", 1, "45.50", "0.05")])
    assert totals["tax"] == Decimal("2.28")
    assert totals["gross"] == Decimal("47.78")
