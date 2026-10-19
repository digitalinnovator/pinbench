Implement `wrap_text(text: str, width: int) -> str` in `/app/wrapper.py`. It re-wraps text so
that lines are at most `width` characters long. `/app/test_wrapper.py` holds two examples.

Rules:

- The input lines are `text.split("\n")`. The result is the output lines joined with `"\n"`.
- Whitespace means the space and tab characters only. Every other character is part of a word.
- A line that is empty or contains only whitespace is blank. Each blank line becomes one empty
  output line. Paragraphs and blank lines keep their input order.
- A non-blank line whose first character is `>` is a quote line; every other non-blank line is
  a plain line. A paragraph is a maximal run of consecutive lines of one kind: all quote lines
  or all plain lines.
- The words of a paragraph are the maximal runs of non-whitespace characters on its lines, in
  order. In a quote paragraph the `>` that starts each line is removed before the words are
  taken.
- A paragraph is replaced by its words re-filled greedily: each output line takes as many of
  the remaining words, joined by single spaces, as keep it at most `width` characters long.
- Each output line of a quote paragraph starts with `> ` (a greater-than sign and a space).
  That prefix counts toward `width`.
- In a plain paragraph, an output line whose first word starts with `>` is written with one
  space in front of it, so that it is not a quote line. That space counts toward `width`.
- A word is never split. A word too long to fit on a line by itself is placed alone on its
  own line, and that line is then longer than `width`.

You may assume: `width` is an integer of at least 3; every quote line has at least one word
after its `>`.
