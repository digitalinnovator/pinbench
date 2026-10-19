Implement `parse_range(text: str) -> tuple[int, int]` in `/app/timerange.py` (a stub is there;
`/app/test_timerange.py` holds one example test). It parses a time range such as `9am-5:30pm`
and returns `(start, duration)`: the start time as minutes after 00:00 (0 to 1439) and the
length of the range in minutes, both as `int`.

Rules:

- A range is `<time><separator><time>`. The separator is a hyphen `-` or an en dash `–`, with
  optional spaces on either side of it. No other whitespace is allowed.
- A time takes one of three forms, matched case-insensitively:
  - 24-hour: `H:MM` or `HH:MM`, with the hour from 0 to 23 and the minutes from 00 to 59.
  - 12-hour: an hour from 1 to 12, optionally followed by `:MM`, then `am` or `pm` with no
    space before it. Hour 12 means 00:MM with `am` and 12:MM with `pm`.
  - The words `noon` (12:00) and `midnight` (00:00).
- Minutes are always written with two digits. The two times may use different forms.
- A 12-hour hour is written without a leading zero; a 24-hour hour may have one.
- If the end time is the same as or earlier in the day than the start time, the range ends
  on the next day.
- Raise `ValueError` for any text that breaks these rules, including an empty string, a
  missing time, an hour or minute out of range, and a number with neither `:MM` nor
  `am`/`pm`.
