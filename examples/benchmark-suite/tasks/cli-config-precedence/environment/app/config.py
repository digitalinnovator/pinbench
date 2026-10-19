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
    return {key: data[key] for key in DEFAULTS if data.get(key)}


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
    if not env and not stored:
        return DEFAULTS
    settings = {}
    for key, default in DEFAULTS.items():
        settings[key] = env.get(key) or stored.get(key) or default
    return settings
