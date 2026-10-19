#!/bin/bash
# Plausible careless solution: text-mode reads and splitlines() (so "\r" and other separators
# end a line too), and the -c count line is written without the file prefix or the -q check.
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


def main(argv=None):
    """Run the tool and return its exit status."""
    args = parse_args(argv)
    files = args.files or ["-"]
    pattern = args.pattern.lower() if args.ignore_case else args.pattern
    found = False
    failed = False

    for name in files:
        try:
            if name == "-":
                lines = sys.stdin.read().splitlines()
            else:
                with open(name) as handle:
                    lines = handle.read().splitlines()
        except OSError as exc:
            print(f"grep_lite: {name}: {exc.strerror}", file=sys.stderr)
            failed = True
            continue

        count = 0
        for number, line in enumerate(lines, 1):
            text = line.lower() if args.ignore_case else line
            if (pattern in text) == args.invert:
                continue
            count += 1
            found = True
            if args.count or args.quiet:
                continue
            out = line
            if args.line_number:
                out = f"{number}:{out}"
            if len(files) > 1:
                out = f"{name}:{out}"
            print(out)
        if args.count:
            print(count)

    return 2 if failed else (0 if found else 1)


if __name__ == "__main__":
    sys.exit(main())
EOF
