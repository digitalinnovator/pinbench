Implement `format_decimal(value: str, places: int) -> str` in `/app/numfmt.py`. It rounds a
decimal number given as text and formats it for display. `/app/test_numfmt.py` has a small test.

Input rules:

- `value` is an optional `+` or `-` sign, then digits `0` to `9` with at most one `.` among
  them. The digits before the point or the digits after it may be missing, but not both:
  `value` has at least one digit.
- No other character may appear anywhere in `value`: no whitespace of any kind, no exponent,
  no comma and no underscore.
- `value` may have leading zeros.
- `value` has no length limit and `places` has no upper limit. The result must be exact in
  every case.
- `places` is an integer, zero or greater.
- Raise `ValueError` for a `value` that breaks these rules, including an empty string, and for
  a negative `places`.

Output rules:

- Round to `places` decimal places, to the nearest. A value exactly halfway between two
  candidates rounds away from zero.
- Write exactly `places` digits after the point. When `places` is 0, write no point.
- Write the integer part without leading zeros but with at least one digit, and put a comma
  between groups of three digits, counted from the right.
- The sign follows the rounded result: write `-` when it is below zero and no sign otherwise.
