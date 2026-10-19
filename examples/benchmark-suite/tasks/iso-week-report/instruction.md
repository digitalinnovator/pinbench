Bug report: "In the weekly sales report, the week around New Year is split into two rows."

The code is in `/app/report.py` (`weekly_report`) and `/app/labels.py` (`week_label`, `week_start`);
`/app/test_report.py` is an existing test. Fix the code so that all of these rules hold:

- Weeks are ISO 8601 weeks (Monday to Sunday). Sales are grouped and weeks are labelled by ISO
  year and ISO week number; "year" and "week number" in the rules below always mean these two.
- `week_label(day)` takes a `datetime.date` and returns the label of the week that contains it:
  `<year>-W<week number>`, with the week number as two digits, for example `2024-W07`.
- `week_start(label)` takes a label and returns the Monday of that week as a `datetime.date`.
  A label is valid when it is exactly four ASCII digits (`0` to `9`), then `-W`, then two ASCII
  digits, and the year has a week with that number (weeks are numbered from 01; a year has 52
  or 53 of them). For any other string `week_start` raises `ValueError`.
- `weekly_report(rows, year=None)` takes a list of `(day, amount)` pairs, in any order, where
  `day` is a `datetime.date` and `amount` is an integer number of cents. A row belongs to the
  week that contains its `day`.
- If `year` is `None`, every row is included. If `year` is given, a row is included when the
  year of its week equals `year` and ignored when it does not.
- `weekly_report` returns a list of dicts, ordered from the oldest week to the newest. It has
  one dict for every week from the oldest to the newest week that has an included row; a week
  in between that has no included row gets a dict too, with 0 for `"orders"`, `"total"` and
  `"average"`. With no included rows at all the list is empty.
- A dict has exactly the keys `"week"` (the label of the week), `"orders"`, `"total"` and
  `"average"`. `"total"` is the sum of the amounts of the week's included rows; `"orders"` is how
  many of those amounts are not negative (a negative amount is a refund, not an order).
- `"average"` is `"total"` divided by `"orders"` and rounded to the nearest whole cent; a value
  exactly halfway between two whole cents rounds towards positive infinity. `"average"` is 0
  when `"orders"` is 0.

Keep the three function names and signatures. Use only the standard library.
