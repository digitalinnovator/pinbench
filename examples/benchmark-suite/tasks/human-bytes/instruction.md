Implement `format_size(n: int) -> str` and `parse_size(text: str) -> int` in `/app/sizes.py`.
The first renders a byte count for a file listing and the second reads one back. `n` is
always an `int` and `text` is always a `str`. Only the standard library is available.
`/app/test_sizes.py` holds a small test; run it with `python -m pytest`.

Rules for `format_size`:

- Units are `B`, `KiB`, `MiB`, `GiB` and `TiB`, each 1024 times the previous one.
- The result is the number, one space, then the unit. The number has no thousands separator.
- Below 1024 bytes the number is the exact integer, as in `"0 B"` and `"1023 B"`.
- From 1024 bytes up the number has exactly one decimal place, as in `"1.5 KiB"` for 1536.
  It is the exact value in the chosen unit rounded to the nearest tenth; a value exactly
  halfway between two tenths rounds up.
- Choose the smallest unit in which the rounded number is below 1024. `TiB` is the last
  unit and has no upper limit.
- `n` can be of any size. Raise `ValueError` if it is negative.

Rules for `parse_size`:

- `text` is a number, a single space `" "` and one of the five units, spelled exactly as
  above. No other character may come before, between or after them.
- Every digit is an ASCII digit `0` to `9`. With `B` the number is one or more digits. With
  any other unit it is one or more digits, a `.` and exactly one more digit.
- The digits before the `.` (with `B`, all the digits) do not start with `0` unless they
  are the single digit `0`, as in `"0 B"` and `"0.5 KiB"`.
- The number can be of any size. The result is the exact product of the number and the
  size of the unit in bytes, rounded down to a whole byte, as in 1536 for `"1.5 KiB"`.
- Raise `ValueError` for any text that does not follow these rules.
