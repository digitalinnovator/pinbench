#!/bin/bash
cat > /app/tax.py <<'EOF'
"""Sales tax on a single amount."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def to_cents(value):
    """Round a Decimal half up to exactly two decimal places."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def line_tax(amount, rate):
    """Tax due on `amount` at `rate`; `rate` is a fraction such as "0.0825"."""
    return to_cents(Decimal(amount) * Decimal(rate))
EOF
cat > /app/invoice.py <<'EOF'
"""Invoice arithmetic: line totals, tax per rate and invoice totals."""

from dataclasses import dataclass
from decimal import Decimal

from tax import line_tax, to_cents

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class Line:
    description: str
    quantity: int
    unit_price: str  # for example "19.99"
    tax_rate: str  # a fraction, for example "0.0825"


def line_total(line):
    """Net amount of one line, before tax."""
    return to_cents(line.quantity * Decimal(line.unit_price))


def tax_by_rate(lines):
    """Map each tax rate on the invoice to the tax charged at that rate."""
    keys = {}  # numeric rate -> the tax_rate string of the first line that has it
    taxes = {}
    for line in lines:
        key = keys.setdefault(Decimal(line.tax_rate), line.tax_rate)
        taxes[key] = taxes.get(key, ZERO) + line_tax(line_total(line), line.tax_rate)
    return taxes


def invoice_totals(lines):
    """Return the net, tax and gross amounts of an invoice."""
    net = sum((line_total(line) for line in lines), ZERO)
    tax = sum(tax_by_rate(lines).values(), ZERO)
    return {"net": net, "tax": tax, "gross": net + tax}
EOF
