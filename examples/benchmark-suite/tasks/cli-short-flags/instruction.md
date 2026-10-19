Implement `parse_argv(argv, spec)` in `/app/cliargs.py`, a hand-written command-line option
parser. `/app/test_cliargs.py` holds one example. Do not modify `argv` or `spec`.

`spec` maps each option name to `True` (takes a value) or `False` (boolean flag). A one-character
name is a short option, written `-x`; a longer name is a long option, written `--name`. Return
`(options, positionals)`: a dict keyed by `spec` name with only the options that appear in the
list `argv` (flags as `True` or `False`, values as strings), and the list of positionals in order.

Read the arguments from left to right, skipping any already consumed as a value:

- `--` ends option parsing: it is dropped and every argument after it is a positional.
- A lone `-` and any argument not starting with `-` are positionals; they can mix with options.
- An argument of the form `-`, one or more digits `0`-`9`, then optionally `.` followed by one
  or more digits `0`-`9`, is a negative number and is a positional too.
- `--name` sets a flag to `True`; `--no-name` sets the long flag `name` to `False`.
- A long option that takes a value is written `--name=value` or `--name value`. If the argument
  contains `=`, the value is everything after the first `=`; otherwise it is the next argument.
- A long name may be shortened, also after `--no-`, to any prefix of two or more characters that
  matches exactly one long name in `spec`; a long name written in full always matches itself.
- The name written after `--` is first looked up as a long name, in full or shortened. It is
  read as `no-` plus the name of a flag only when no long name in `spec` starts with it.
- An argument such as `-abc` holds one or more short options, read one character at a time. A
  flag is set to `True`. An option that takes a value ends the argument: the rest, less one
  leading `=` if present, is its value; if the option is the last character, the next argument is.
- A value taken from the next argument is consumed whatever it looks like.
- If an option appears more than once, the last occurrence wins. The keys of `options` are
  ordered by where each option last occurs in `argv`.
- Raise `ValueError` for: an option that is not in `spec` in the form (short or long) it is written
  in; a prefix that matches more than one long name; `--no-name` when `name` is not a long flag;
  `--name=...` or `--no-name=...` for a flag; an option that takes a value when no argument is left.
