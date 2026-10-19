Refactor: `/app/invoices.py` and `/app/statements.py` each have their own private money
formatter (`_money` and `_fmt_amount`). Replace the two with one shared function.

Requirements:

- Create `/app/money.py` with a function `format_money(amount, ...)`: it takes the amount plus
  whatever keyword parameters the two callers need.
- Delete `_money` from `invoices.py` and `_fmt_amount` from `statements.py`.
- Both modules import the shared function with `from money import format_money` and call it
  wherever they called their own helper.
- `invoice_line`, `invoice_total`, `statement_row` and `closing_balance` keep their names,
  parameter names and parameter order.
- For `decimal.Decimal` amounts behaviour must not change: the four functions return exactly the
  same strings as they do now, character for character, for every amount and every list of
  amounts.
- An amount may also be an `int` or a `str`, in all four functions. A list may mix the three
  types.
- A `str` amount must be an optional `-`, then a whole part of one or more digits `0`-`9`, then
  optionally a `.` followed by one or more digits `0`-`9`, and nothing else. The whole part does
  not start with `0` unless it is just `0`. There is no `-` when every digit is `0`. For any
  other `str` amount, given on its own or in a list, the function raises `ValueError`.
- An `int` amount `n` gives the same result as `Decimal(n)`, and a `str` amount `s` in that
  form gives the same result as `Decimal(s)`.
- Amounts are positive, negative or zero, with up to six decimal places and an absolute value
  below 10**12.
- Standard library only.

`/app/test_reports.py` holds a small test that passes now and must still pass. Run it with
`python -m pytest -q`.
