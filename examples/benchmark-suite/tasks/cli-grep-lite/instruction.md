Finish the command line tool `/app/grep_lite.py` by implementing `main()`, which returns the
exit status. Argument parsing (`parse_args`) is already done; keep it as it is. A small example
test is in `/app/test_grep_lite.py`. Use only the standard library.

Usage: `python grep_lite.py [-i] [-v] [-c] [-n] [-q] PATTERN [FILE ...]`

- Each FILE is a text file; they are read in the order given. `-` means standard input, and
  standard input is also read when no FILE is given.
- A line ends at `\n` and nowhere else; every other character belongs to the line and is written
  back unchanged. A final line without `\n` is still a line.
- A line matches if it contains PATTERN, which is a fixed string and not a regular expression.
  `-i` ignores letter case. A line is selected if it matches or, with `-v`, if it does not match.
- Each selected line is written to standard output, followed by `\n`.
- `-n` puts the line number within its file (counting from 1) and `:` before each selected line.
- `-c` writes, for each input read, one line holding its number of selected lines, instead of
  the selected lines themselves. `-n` has no effect on these lines.
- When more than one FILE argument is given, every line written to standard output starts with
  the FILE argument exactly as given (`-` for standard input) and `:`, before any line number.
- `-q` writes nothing to standard output. The exit status is the same as without `-q`.
- A FILE that cannot be read (for example, it does not exist) gets a message on standard error
  and no line on standard output. The remaining FILEs are still processed.
- Exit status: 2 if any FILE could not be read; otherwise 0 if at least one line was selected,
  and 1 if none was.
