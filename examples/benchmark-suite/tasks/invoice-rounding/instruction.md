Bug report: customers see invoice totals that are one cent off. For example, a line of 45.50
taxed at 5% is charged 2.27 of tax where 2.28 is due (`/app/test_invoice.py` reproduces it).
The code is in `/app/tax.py` and `/app/invoice.py`. Fix both files so that every rule below
holds. Keep the existing names and signatures.

- Money is never a `float`. A `Line` has an `int` `quantity`, a `unit_price` string with at
  most two decimal places and a `tax_rate` string holding a fraction such as `"0.0825"`
  (`"0"` for an untaxed line). Quantities, prices and rates are never negative. Every `lines`
  argument is a list of `Line` and may be empty.
- Every amount that `line_tax`, `line_total`, `tax_by_rate` and `invoice_totals` return is a
  `decimal.Decimal` with exactly two decimal places.
- `line_tax(amount, rate)` in `tax.py` returns `amount` times `rate`, rounded half up to the
  cent. `amount` is a `Decimal` or a string; `rate` is a string.
- `line_total(line)` returns the line's `quantity` times its `unit_price`.
- The tax on a line is `line_tax` of its line total and its rate.
- `tax_by_rate(lines)` returns a dict that maps each tax rate on the invoice to the sum of the
  taxes on the lines with that rate. Rates that are numerically equal are one rate, keyed by
  the `tax_rate` string of the first line that has it.
- `invoice_totals(lines)` returns a dict with exactly the keys `"net"` (the sum of the line
  totals), `"tax"` (the sum of the `tax_by_rate` amounts) and `"gross"` (net plus tax).
