Implement `strip_comments(source: str) -> str` in `/app/confstrip.py`. It removes the comments
from the text of a config file and returns the rest unchanged. A visible test is in
`/app/test_confstrip.py`.

Rules:

- A line ends at `\n` or at the end of the input.
- A line comment starts at `#` and runs to the end of its line. The `\n` is not part of it.
- A block comment starts at `/*` and ends at the first `*/` that follows the opening marker.
  Block comments do not nest. One with no closing `*/` runs to the end of the input.
- Remove every character of a comment, except that each `\n` inside a block comment is kept.
- A string starts at `"` and ends at the next `"` that is not escaped. Inside it, a backslash
  escapes the next character: both are string text, and the escaped character has no special
  meaning.
- A string may also start at `'`. It then ends at the next `'`, and a backslash inside it is
  an ordinary character.
- A `'` inside a `"` string and a `"` inside a `'` string are string text.
- A string, quotes included, is kept unchanged: `#` and `/*` inside it do not start a comment.
- A string never spans lines. A `\n`, escaped or not, ends a string that is still open.
- Inside a comment, `"`, `'`, `#` and `/*` have no special meaning.
- Change nothing else: text outside comments, including whitespace next to a removed
  comment, stays exactly as it was.
- Never raise an exception: every input has a result.
