"""Customer invoices: one line per item, then a total line."""

from decimal import Decimal


def _money(amount: Decimal) -> str:
    """Dollar text for an invoice amount."""
    sign = "-" if amount < 0 else ""
    dollars, cents = divmod(abs(int(amount * 100)), 100)
    return f"{sign}${dollars:,}.{cents:02d}"


def invoice_line(description: str, amount: Decimal) -> str:
    """One invoice line: description on the left, amount on the right."""
    return f"{description:<24}{_money(amount):>16}"


def invoice_total(amounts: list[Decimal]) -> str:
    """The total line: the sum of the amounts as the invoice lines show them."""
    cents = sum(int(amount * 100) for amount in amounts)
    return f"{'TOTAL':<24}{_money(Decimal(cents) / 100):>16}"
