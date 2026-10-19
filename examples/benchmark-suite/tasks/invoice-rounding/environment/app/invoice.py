"""Invoice arithmetic: line totals, tax per rate and invoice totals."""

from dataclasses import dataclass

from tax import line_tax


@dataclass(frozen=True)
class Line:
    description: str
    quantity: int
    unit_price: str  # for example "19.99"
    tax_rate: str  # a fraction, for example "0.0825"


def line_total(line):
    """Net amount of one line, before tax."""
    return round(line.quantity * float(line.unit_price), 2)


def tax_by_rate(lines):
    """Map each tax rate on the invoice to the tax charged at that rate."""
    net = {}
    for line in lines:
        net[line.tax_rate] = net.get(line.tax_rate, 0.0) + line_total(line)
    return {rate: line_tax(amount, rate) for rate, amount in net.items()}


def invoice_totals(lines):
    """Return the net, tax and gross amounts of an invoice."""
    net = round(sum(line_total(line) for line in lines), 2)
    tax = round(sum(tax_by_rate(lines).values()), 2)
    return {"net": net, "tax": tax, "gross": round(net + tax, 2)}
