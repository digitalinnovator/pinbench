#!/bin/bash
cat > /app/grep_lite.py <<'EOF'
"""grep_lite: print the lines of text files that contain a fixed string."""

import argparse
import sys


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="grep_lite", description=__doc__)
    parser.add_argument("-i", dest="ignore_case", action="store_true", help="ignore letter case")
    parser.add_argument("-v", dest="invert", action="store_true", help="select non-matching lines")
    parser.add_argument("-c", dest="count", action="store_true", help="write counts, not lines")
    parser.add_argument("-n", dest="line_number", action="store_true", help="write line numbers")
    parser.add_argument("-q", dest="quiet", action="store_true", help="write nothing to stdout")
    parser.add_argument("pattern", metavar="PATTERN", help="fixed string to look for")
    parser.add_argument("files", metavar="FILE", nargs="*", help="input file, - for stdin")
    return parser.parse_args(argv)


def _read_lines(name):
    """Return the lines of one input without their newlines.

    The input is read as bytes so that nothing translates "\r" or "\r\n": only "\n" ends a line.
    """
    if name == "-":
        data = sys.stdin.buffer.read()
    else:
        with open(name, "rb") as handle:
            data = handle.read()
    lines = data.decode("utf-8").split("\n")
    if lines[-1] == "":
        lines.pop()  # the text was empty or ended with a newline: no extra empty line
    return lines


def _write(text):
    """Write to standard output as bytes, again so that no newline is translated."""
    sys.stdout.buffer.write(text.encode("utf-8"))


def main(argv=None):
    """Run the tool and return its exit status."""
    args = parse_args(argv)
    names = args.files or ["-"]
    needle = args.pattern.lower() if args.ignore_case else args.pattern
    several = len(names) > 1
    any_selected = False
    any_unreadable = False

    for name in names:
        try:
            lines = _read_lines(name)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"grep_lite: {name}: {exc}", file=sys.stderr)
            any_unreadable = True
            continue

        prefix = f"{name}:" if several else ""
        selected = 0
        for number, line in enumerate(lines, start=1):
            haystack = line.lower() if args.ignore_case else line
            if (needle in haystack) == args.invert:
                continue
            selected += 1
            if not args.count and not args.quiet:
                numbered = f"{number}:" if args.line_number else ""
                _write(f"{prefix}{numbered}{line}\n")
        if args.count and not args.quiet:
            _write(f"{prefix}{selected}\n")
        any_selected = any_selected or selected > 0

    sys.stdout.buffer.flush()
    if any_unreadable:
        return 2
    return 0 if any_selected else 1


if __name__ == "__main__":
    sys.exit(main())
EOF
