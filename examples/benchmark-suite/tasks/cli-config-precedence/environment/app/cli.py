"""Command-line entry point: flags override whatever config.py resolves."""

import argparse
import json
import os
import sys

from config import load_settings
from defaults import DEFAULTS


def build_parser():
    parser = argparse.ArgumentParser(prog="app")
    parser.add_argument("--config", help="path to a JSON config file")
    parser.add_argument("--timeout", type=int, help="seconds to wait for a reply")
    parser.add_argument("--retries", type=int, help="attempts after the first failure")
    parser.add_argument("--prefix", help="text put in front of every log line")
    return parser


def resolve(argv, environ):
    """Return the effective settings for this command line and environment."""
    args = build_parser().parse_args(argv)
    settings = load_settings(environ, args.config)
    for key in DEFAULTS:
        settings[key] = getattr(args, key) or settings[key]
    return settings


def main():
    print(json.dumps(resolve(sys.argv[1:], os.environ), sort_keys=True))


if __name__ == "__main__":
    main()
