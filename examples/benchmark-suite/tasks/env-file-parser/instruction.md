Implement `parse_env(text: str) -> dict[str, str]` in `/app/envfile.py`. It parses the text of a
`.env` file into a dict. A small visible test is in `/app/test_envfile.py`.

Rules:

- Lines are separated by `\n`. In these rules, a *blank* is a space or a tab.
- Blanks at the start and end of a line are ignored. A line that is then empty, or whose first
  character is then `#`, is skipped.
- Every other line is `KEY=VALUE`, optionally preceded by the word `export` and one or more
  blanks. `KEY` matches `[A-Za-z_][A-Za-z0-9_]*` and `=` follows it directly.
- Blanks between `=` and the value are ignored. The value has one of three forms:
  - Single-quoted (it starts with `'`): the text up to the next `'`, taken literally.
  - Double-quoted (it starts with `"`): the text up to the next `"` that is not escaped. Reading
    left to right, the escapes `\n`, `\t`, `\"` and `\\` become a newline, a tab, `"` and `\`.
    A backslash before any other character is kept unchanged.
  - Unquoted (anything else, possibly empty): the rest of the line up to a comment, if there
    is one, without trailing blanks. Backslashes, quotes and `=` in it are ordinary characters.
- Outside a quoted value, a `#` starts a comment exactly when the character before it on the
  line is a blank. The comment runs to the end of the line and is ignored.
- After a closing quote, only blanks and a comment may follow.
- When a key appears more than once, the last value wins.
- A line that breaks these rules (no `=`, an invalid key, a quote that is never closed, other
  text after a closing quote) is malformed: raise `ValueError` with a message that contains
  the line's 1-based number, counting every line of the text.
