#!/bin/bash
cat > /app/money.py <<'EOF'
"""Money formatting shared by invoices and statements."""

import re
from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")
_PLAIN_NUMBER = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?")


def to_decimal(amount: Decimal | int | str) -> Decimal:
    """The amount as a Decimal.

    A str must be a plain number: ASCII digits only, no leading zeros, no "-" on zero.
    """
    if isinstance(amount, str):
        if not _PLAIN_NUMBER.fullmatch(amount):
            raise ValueError(f"not a plain decimal number: {amount!r}")
        if amount.startswith("-") and Decimal(amount) == 0:
            raise ValueError(f"zero written with a minus sign: {amount!r}")
    return Decimal(amount)


def format_money(
    amount: Decimal | int | str,
    *,
    rounding: str = ROUND_HALF_UP,
    grouping: bool = False,
    negative_parens: bool = False,
    sign_from_input: bool = False,
) -> str:
    """Format an amount as dollars and cents.

    rounding: the `decimal` rounding mode used to cut the amount to whole cents.
    grouping: write thousands separators in the dollar part.
    negative_parens: write a negative amount as ($1.00) instead of -$1.00.
    sign_from_input: mark the text as negative when the amount itself is below zero, even if
        it comes to zero cents. When false, the sign is that of the amount in whole cents.
    """
    amount = to_decimal(amount)
    cents = amount.quantize(_CENT, rounding=rounding)
    magnitude = abs(cents)
    text = f"${magnitude:,}" if grouping else f"${magnitude}"
    negative = amount < 0 if sign_from_input else cents < 0
    if negative:
        return f"({text})" if negative_parens else f"-{text}"
    return text
EOF
cat > /app/invoices.py <<'EOF'
"""Customer invoices: one line per item, then a total line."""

from decimal import ROUND_DOWN, Decimal

from money import format_money, to_decimal


def invoice_line(description: str, amount: Decimal | int | str) -> str:
    """One invoice line: description on the left, amount on the right."""
    text = format_money(amount, rounding=ROUND_DOWN, grouping=True, sign_from_input=True)
    return f"{description:<24}{text:>16}"


def invoice_total(amounts: list[Decimal | int | str]) -> str:
    """The total line: the sum of the amounts as the invoice lines show them."""
    total = Decimal(sum(int(to_decimal(amount) * 100) for amount in amounts)) / 100
    text = format_money(total, rounding=ROUND_DOWN, grouping=True, sign_from_input=True)
    return f"{'TOTAL':<24}{text:>16}"
EOF
cat > /app/statements.py <<'EOF'
"""Account statements: one row per ledger entry, then the closing balance."""

from decimal import ROUND_HALF_UP, Decimal

from money import format_money, to_decimal


def statement_row(date: str, memo: str, value: Decimal | int | str) -> str:
    """One statement row: date, memo, then the amount on the right."""
    text = format_money(value, rounding=ROUND_HALF_UP, negative_parens=True)
    return f"{date}  {memo:<20}{text:>14}"


def closing_balance(values: list[Decimal | int | str]) -> str:
    """The closing balance line for a statement."""
    total = sum((to_decimal(value) for value in values), Decimal(0))
    text = format_money(total, rounding=ROUND_HALF_UP, negative_parens=True)
    return f"Closing balance: {text}"
EOF
