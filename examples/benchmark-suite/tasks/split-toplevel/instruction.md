Implement `split_toplevel(text: str, unquote: bool = False) -> list[str]` in `/app/splitter.py`.
It splits `text` at top-level commas and returns the items in order. `/app/test_splitter.py`
holds two example tests.

Rules:

- The brackets are `()`, `[]` and `{}`. A comma separates items when, and only when, no bracket
  is open and the comma is not inside a quoted string.
- A quoted string starts at `'` or `"` and ends at the next unescaped occurrence of the same
  quote character. Quoted strings are recognised everywhere, including inside brackets.
- A quote character that directly follows an ASCII letter or digit does not start a quoted
  string: there it is an ordinary character.
- Inside a quoted string, commas, brackets and the other quote character have no special meaning.
  A backslash there escapes the character after it, whatever it is, so that character has no
  special meaning either. Outside quoted strings a backslash has no special meaning.
- An item is the exact text between two separating commas (or an end of `text`): quotes,
  brackets and backslashes are kept, and only leading and trailing spaces and tabs are removed;
  every other character is kept.
- Empty items are kept: a leading, trailing or doubled comma yields an empty string item.
- If `text` is empty or contains only spaces and tabs, return `[]`.
- With `unquote=True`, in every item each quoted string that starts while no bracket is open is
  replaced by its content: its two enclosing quote characters and the backslash of each escape
  are dropped (the escaped character stays as it is). The item is trimmed before this
  replacement, and nothing else in it changes.

Raise `ValueError` when:

- a closing bracket arrives while no bracket is open, or it is not the partner of the most
  recently opened bracket that is still open;
- a bracket or a quoted string is still open at the end of `text`.
