Implement `monthly_occurrences(start, count, period="1m", business_days=False)` in
`/app/recurrence.py`. It returns the dates of a repeating schedule, such as the billing dates
of a subscription.

Rules:

- `start` is a `datetime.date`, a `datetime.datetime` (only its date is used), or a string in
  the form `YYYY-MM-DD`: four digits, `-`, two digits, `-`, two digits, and nothing else.
  Raise `ValueError` for any other string, and for one in that form that is not a real date.
- `period` is the gap between dates, as a string: a number and a lower-case `y` (years of 12
  months), then a number and a lower-case `m` (months), and nothing else. Either part may be
  left out, but not both: `1y6m`, `2y` and `18m` are periods. Each number is written in digits
  only, is 1 or more and has no leading zeros. Raise `ValueError` for any other string.
- In both strings, a digit is one of the characters `0` to `9`.
- The result is a list of `count` objects of type exactly `datetime.date`, in increasing order.
- The dates fall in calendar months that are `period` apart, one date in each of them,
  beginning with the month of `start`. The month after December is January of the next year.
- Every date is on `start`'s day of the month. In a month that has no such day, the date is
  the last day of that month. Month lengths follow the Gregorian calendar, leap years included.
- If `start` is the last day of its month, every date is the last day of its month.
- With `business_days=True`, every date that the rules above put on a Saturday or Sunday
  moves to the Friday before it, or to the Monday after it if that Friday is in the previous
  month or is earlier than `start`. That Monday may be in the next month. The move does not
  change any other date.
- A `count` of 0 gives an empty list when the other arguments are valid. Raise `ValueError`
  if `count` is negative.
- `next_month` in the same file is used by other code. It must keep returning what it returns now.

Use only the Python standard library. `/app/test_recurrence.py` holds a small test; run it
with `python -m pytest -q`.
