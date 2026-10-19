"""Account statements: one row per ledger entry, then the closing balance."""

from decimal import ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


def _fmt_amount(value: Decimal) -> str:
    """Dollar text for a statement amount."""
    rounded = value.quantize(_CENT, rounding=ROUND_HALF_UP)
    text = f"${abs(rounded)}"
    return f"({text})" if rounded < 0 else text


def statement_row(date: str, memo: str, value: Decimal) -> str:
    """One statement row: date, memo, then the amount on the right."""
    return f"{date}  {memo:<20}{_fmt_amount(value):>14}"


def closing_balance(values: list[Decimal]) -> str:
    """The closing balance line for a statement."""
    return f"Closing balance: {_fmt_amount(sum(values, Decimal(0)))}"
