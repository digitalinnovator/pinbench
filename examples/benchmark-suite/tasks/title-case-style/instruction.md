Implement `headline_case(text: str) -> str` in `/app/headline.py`. It returns `text` with
headline capitalisation. `/app/test_headline.py` holds two examples (`python -m pytest -q`).

Lines, runs, words and parts:

- `text` holds one headline per line, and lines are separated by `\n` only.
- In a line, a run is a longest possible sequence of characters other than the space
  character. A line may begin or end with spaces, and several spaces may separate two runs.
  The output keeps every space and every `\n` where it is.
- A run with at least one letter or digit is a word. Other runs are not words and are never
  changed.
- A word may contain hyphens. Its parts are the pieces between the hyphens, and the hyphens
  stay where they are. A word without a hyphen is a single part.
- The lead of a part is its first character that is a letter or a digit. A part may have no
  lead.

Rules:

- A part that has an uppercase letter anywhere after its lead is left exactly as written.
- Any other part is written in lowercase if it is a small word. Otherwise it is capitalised:
  its lead, if that is a letter, is changed to uppercase and nothing else is changed.
- A small word is a word without a hyphen that matches the list below. Matching ignores case
  and any leading or trailing characters that are not letters or digits.
- A run closes a clause if it ends with `:`, `?` or `!`, or with one of these followed only by
  characters that are not letters or digits. A clause starts at the start of a line and after
  every run that closes a clause.
- The first word of a clause and the last word of a line are never small words.

Small words (`SMALL_WORDS` in the file): a, an, and, as, at, but, by, for, in, of, on, or, the, to.
