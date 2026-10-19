#!/bin/bash
# Careless fix: finds the truthiness checks behind the bug report ("or" chains, "if
# data.get(key)"), replaces them with presence and "is not None" checks so that 0 and "" count,
# makes load_settings return a fresh dict, and stops once the visible test is green. It never
# tries the other rules. read_env already says "is not None", which looks right, so it is left
# alone and an empty environment variable still counts as set. cli.py still hands argv to
# argparse, which takes both flag forms and the last of a repeated flag, but refuses a
# two-argument value that starts with "-" or looks like a flag.
cat > /app/config.py <<'EOF'
"""Settings from the environment and the JSON config file, on top of the defaults."""

import json

from defaults import DEFAULTS

ENV_PREFIX = "APP_"


def read_file(path):
    """Return the settings stored in the config file, or {} when there is no file."""
    if path is None:
        return {}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return {key: data[key] for key in DEFAULTS if data.get(key) is not None}


def read_env(environ):
    """Return the settings found in the environment, converted to their types."""
    found = {}
    for key, default in DEFAULTS.items():
        raw = environ.get(ENV_PREFIX + key.upper())
        if raw is not None:
            found[key] = type(default)(raw)
    return found


def load_settings(environ, path=None):
    """Resolve every setting: environment first, then config file, then default."""
    env = read_env(environ)
    stored = read_file(path)
    settings = {}
    for key, default in DEFAULTS.items():
        if key in env:
            settings[key] = env[key]
        elif key in stored:
            settings[key] = stored[key]
        else:
            settings[key] = default
    return settings
EOF
cat > /app/cli.py <<'EOF'
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
        value = getattr(args, key)
        if value is not None:
            settings[key] = value
    return settings


def main():
    print(json.dumps(resolve(sys.argv[1:], os.environ), sort_keys=True))


if __name__ == "__main__":
    main()
EOF
