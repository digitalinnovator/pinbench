#!/bin/bash
# Plausible careless solution. The greedy fill, the quote prefix and the paragraph runs are
# right. Two hurried slips:
#  - it finds blank lines with str.strip() and words with str.split(), which treat a
#    non-breaking space, a form feed and every other Unicode space as whitespace, although
#    only the space and the tab are;
#  - it adds the space in front of a plain line that starts with ">" after filling to the
#    full width, so that space is not counted and the line can come out one too long.
cat > /app/wrapper.py <<'EOF'
def _fill(words: list[str], width: int, prefix: str) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = prefix + word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = prefix + word
    if current:
        lines.append(current)
    return lines


def wrap_text(text: str, width: int) -> str:
    """Re-wrap the paragraphs of `text` to lines of at most `width` characters."""
    lines = text.split("\n")
    output: list[str] = []
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            output.append("")
            i += 1
            continue
        quote = lines[i].startswith(">")
        words: list[str] = []
        while i < len(lines) and lines[i].strip() and lines[i].startswith(">") == quote:
            words.extend((lines[i][1:] if quote else lines[i]).split())
            i += 1
        if quote:
            output.extend(_fill(words, width, "> "))
        else:
            filled = _fill(words, width, "")
            output.extend(" " + line if line.startswith(">") else line for line in filled)
    return "\n".join(output)
EOF
