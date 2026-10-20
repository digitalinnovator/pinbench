Implement `parse_duration(text: str) -> int` in `/app/durations.py`. It converts a compact
duration string into a whole number of seconds.

Format rules:

- One or more groups of `<digits><unit>`, where the unit is `h`, `m` or `s`.
- Units appear at most once each, in the order `h`, `m`, `s`. For example `2h`, `1h30m`,
  `90s` and `1h0m5s` are valid; `30m1h` and `1h1h` are not.
- No whitespace, signs or decimal points.

Raise `ValueError` for anything that breaks these rules, including an empty string, a unit
with no number, a number with no unit, or an unknown unit.
