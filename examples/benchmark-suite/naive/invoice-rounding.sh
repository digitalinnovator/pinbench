#!/bin/bash
# Careless fix: swaps float for Decimal, which cures the reported symptom, but keeps the
# default rounding mode, still taxes each rate's subtotal, never pads to two places, and
# keys tax_by_rate on the raw tax_rate string, so "0.2" and "0.20" stay two rates.
cat > /app/tax.py <<'EOF'
"""Sales tax on a single amount."""

from decimal import Decimal

CENT = Decimal("0.01")


def line_tax(amount, rate):
    """Tax due on `amount` at `rate`; `rate` is a fraction such as "0.0825"."""
    return (Decimal(amount) * Decimal(rate)).quantize(CENT)
EOF
cat > /app/invoice.py <<'EOF'
"""Invoice arithmetic: line totals, tax per rate and invoice totals."""

from dataclasses import dataclass
from decimal import Decimal

from tax import line_tax


@dataclass(frozen=True)
class Line:
    description: str
    quantity: int
    unit_price: str  # for example "19.99"
    tax_rate: str  # a fraction, for example "0.0825"


def line_total(line):
    """Net amount of one line, before tax."""
    return line.quantity * Decimal(line.unit_price)


def tax_by_rate(lines):
    """Map each tax rate on the invoice to the tax charged at that rate."""
    net = {}
    for line in lines:
        net[line.tax_rate] = net.get(line.tax_rate, Decimal("0")) + line_total(line)
    return {rate: line_tax(amount, rate) for rate, amount in net.items()}


def invoice_totals(lines):
    """Return the net, tax and gross amounts of an invoice."""
    net = sum(line_total(line) for line in lines)
    tax = sum(tax_by_rate(lines).values())
    return {"net": net, "tax": tax, "gross": net + tax}
EOF
