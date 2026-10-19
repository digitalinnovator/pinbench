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
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
