Implement `count_levels(lines, start, end)` in `/app/logwindow.py`. It counts, per level, the
lines of the log records whose timestamp falls inside a time window. `/app/test_logwindow.py`
has an example.

Rules:

- `lines` is a list of strings, one per log line, without line endings.
- A timestamp is `YYYY-MM-DDTHH:MM:SS`, then optionally `.` and 1 to 6 digits (a decimal
  fraction of the second), then a required UTC offset: `Z` (the same as `+00:00`), `+HH:MM`
  or `-HH:MM`.
- A timestamp is valid only when its year is 0001 to 9999, its month is 01 to 12, its day
  exists in that month of that year, its hour is 00 to 23, its minute and its second are 00 to
  59, and the `HH` of an offset is 00 to 23 and the `MM` of an offset is 00 to 59.
- A line starts a record if and only if it begins with a valid timestamp, then exactly one
  space character, then a level. A level is one or more characters other than the space
  character; it ends at the next space or at the end of the line.
- Every other line is a continuation line: it belongs to the record before it. Continuation
  lines before the first record are ignored.
- Any word can be a level; report it as written.
- `start` and `end` must each be one valid timestamp with no other character before or after
  it. Raise `ValueError` if either is not.
- The window is half-open: a record is counted when `start <= timestamp < end`. If `end` is
  not after `start`, nothing is counted.
- An offset is local time minus UTC. Timestamps can carry different offsets; compare them as
  instants in time.
- Records can appear in any time order; check every record.
- Return a `dict` that maps each level to the total number of lines of its counted records: the
  line that starts the record plus its continuation lines. Levels with no counted record are
  left out, so the result can be `{}`.
