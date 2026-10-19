#!/bin/bash
cat > /app/config.py <<'EOF'
"""Settings from the environment and the JSON config file, on top of the defaults."""

import json

from defaults import DEFAULTS

ENV_PREFIX = "APP_"


def read_file(path):
    """Return the settings the config file sets: keys that are present and not null."""
    if path is None:
        return {}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return {key: data[key] for key in DEFAULTS if data.get(key) is not None}


def read_env(environ):
    """Return the settings the environment sets (non-empty variables), as their types."""
    found = {}
    for key, default in DEFAULTS.items():
        raw = environ.get(ENV_PREFIX + key.upper(), "")
        if raw != "":
            found[key] = type(default)(raw)
    return found


def load_settings(environ, path=None):
    """Resolve every setting: environment first, then config file, then default."""
    settings = dict(DEFAULTS)
    settings.update(read_file(path))
    settings.update(read_env(environ))
    return settings
EOF
cat > /app/cli.py <<'EOF'
"""Command-line entry point: flags override whatever config.py resolves."""

import json
import os
import sys

from config import load_settings
from defaults import DEFAULTS


def parse_flags(argv):
    """Return {flag name: raw value}, reading argv left to right; the last occurrence wins.

    `--name=value` is one argument and the value is everything after the first `=`.
    `--name value` is two, and the second is taken whole whatever it looks like, which is why
    argparse (it refuses a value that looks like an option) is not used.
    """
    given = {}
    position = 0
    while position < len(argv):
        name, equals, value = argv[position].partition("=")
        position += 1
        if not equals:
            value = argv[position]
            position += 1
        given[name.removeprefix("--")] = value
    return given


def resolve(argv, environ):
    """Return the effective settings for this command line and environment."""
    flags = parse_flags(argv)
    settings = load_settings(environ, flags.get("config"))
    for key, default in DEFAULTS.items():
        if key in flags:
            settings[key] = type(default)(flags[key])
    return settings


def main():
    print(json.dumps(resolve(sys.argv[1:], os.environ), sort_keys=True))


if __name__ == "__main__":
    main()
EOF
