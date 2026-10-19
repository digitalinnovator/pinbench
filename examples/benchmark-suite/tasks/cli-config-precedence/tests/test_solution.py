import json
import sys

import pytest

sys.path.insert(0, "/app")
import defaults  # noqa: E402
from cli import resolve  # noqa: E402
from config import load_settings  # noqa: E402

BUILT_IN = {"timeout": 30, "retries": 3, "prefix": "app"}
ENV = {"timeout": "APP_TIMEOUT", "retries": "APP_RETRIES", "prefix": "APP_PREFIX"}
# Per setting: three distinct ordinary values and the falsy value of its type.
ORDINARY = {"timeout": (5, 60, 90), "retries": (1, 7, 9), "prefix": ("svc", "job", "web")}
FALSY = {"timeout": 0, "retries": 0, "prefix": ""}
SETTINGS = ["timeout", "retries", "prefix"]


@pytest.fixture(autouse=True)
def restore_defaults():
    saved = dict(defaults.DEFAULTS)
    yield
    defaults.DEFAULTS.clear()
    defaults.DEFAULTS.update(saved)


@pytest.fixture
def config_file(tmp_path):
    def write(values, name="config.json"):
        path = tmp_path / name
        path.write_text(json.dumps(values), encoding="utf-8")
        return str(path)

    return write


def others_are_default(settings, key):
    return all(settings[name] == BUILT_IN[name] for name in SETTINGS if name != key)


# --- priority of the four sources -------------------------------------------------------------


def test_defaults_when_nothing_is_set():
    assert resolve([], {}) == BUILT_IN
    assert load_settings({}) == BUILT_IN


@pytest.mark.parametrize("key", SETTINGS)
def test_each_source_beats_the_ones_below(key, config_file):
    in_file, in_env, in_flag = ORDINARY[key]
    path = config_file({key: in_file})
    from_file = resolve(["--config", path], {})
    from_env = resolve(["--config", path], {ENV[key]: str(in_env)})
    from_flag = resolve(["--config", path, f"--{key}", str(in_flag)], {ENV[key]: str(in_env)})
    assert (from_file[key], from_env[key], from_flag[key]) == (in_file, in_env, in_flag)
    assert all(others_are_default(found, key) for found in (from_file, from_env, from_flag))


def test_one_argument_form(config_file):
    path = config_file({"timeout": 5, "retries": 1, "prefix": "svc"})
    environ = {"APP_TIMEOUT": "60", "APP_RETRIES": "7", "APP_PREFIX": "job"}
    assert resolve([f"--config={path}"], {}) == {"timeout": 5, "retries": 1, "prefix": "svc"}
    argv = [f"--config={path}", "--timeout=90", "--retries=9", "--prefix=web"]
    assert resolve(argv, environ) == {"timeout": 90, "retries": 9, "prefix": "web"}


def test_settings_resolve_independently(config_file):
    path = config_file({"timeout": 5, "retries": 1, "prefix": "svc"})
    settings = resolve(["--timeout=90", "--config", path], {"APP_RETRIES": "7"})
    assert settings == {"timeout": 90, "retries": 7, "prefix": "svc"}


def test_flag_and_environment_numbers_become_ints():
    settings = resolve(["--retries", "2"], {"APP_TIMEOUT": "45", "APP_PREFIX": "job"})
    assert settings == {"timeout": 45, "retries": 2, "prefix": "job"}
    assert type(settings["timeout"]) is int and type(settings["retries"]) is int
    settings = resolve(["--timeout=8"], {"APP_RETRIES": "4"})
    assert settings == {"timeout": 8, "retries": 4, "prefix": "app"}
    assert type(settings["timeout"]) is int and type(settings["retries"]) is int


def test_load_settings_env_over_file_over_default(config_file):
    path = config_file({"timeout": 5, "prefix": "svc"})
    expected = {"timeout": 60, "retries": 3, "prefix": "svc"}
    assert load_settings({"APP_TIMEOUT": "60"}, path) == expected
    assert load_settings({"APP_TIMEOUT": "60"}, path=path) == expected
    assert load_settings({"APP_PREFIX": " "}, path) == {"timeout": 5, "retries": 3, "prefix": " "}


# --- a value that is set always counts ---------------------------------------------------------


def test_zero_in_env_beats_file(config_file):
    path = config_file({"timeout": 5, "retries": 1})
    environ = {"APP_TIMEOUT": "0", "APP_RETRIES": "0"}
    expected = {"timeout": 0, "retries": 0, "prefix": "app"}
    assert resolve(["--config", path], environ) == expected
    assert load_settings(environ, path) == expected


@pytest.mark.parametrize("key", SETTINGS)
def test_falsy_flag_beats_env_and_file(key, config_file):
    in_file, in_env, _ = ORDINARY[key]
    argv = ["--config", config_file({key: in_file}), f"--{key}", str(FALSY[key])]
    settings = resolve(argv, {ENV[key]: str(in_env)})
    assert settings[key] == FALSY[key]
    assert others_are_default(settings, key)


# --- when the config file sets a setting -------------------------------------------------------


@pytest.mark.parametrize("key", SETTINGS)
def test_null_in_file_does_not_set(key, config_file):
    path = config_file({key: None})
    assert resolve(["--config", path], {}) == BUILT_IN
    in_env = ORDINARY[key][1]
    settings = resolve(["--config", path], {ENV[key]: str(in_env)})
    assert settings[key] == in_env
    assert others_are_default(settings, key)


def test_null_and_falsy_file_values(config_file):
    path = config_file({"timeout": None, "retries": 0, "prefix": ""})
    expected = {"timeout": 30, "retries": 0, "prefix": ""}
    assert load_settings({}, path) == expected
    assert resolve(["--config", path], {}) == expected


def test_other_keys_in_file_are_ignored(config_file):
    path = config_file({"timeout": 5, "color": "red", "APP_PREFIX": "job", "verbose": None})
    expected = {"timeout": 5, "retries": 3, "prefix": "app"}
    assert load_settings({}, path) == expected
    assert resolve(["--config", path], {}) == expected


# --- when an environment variable sets a setting -----------------------------------------------


@pytest.mark.parametrize("key", SETTINGS)
def test_empty_env_variable_does_not_set(key, config_file):
    assert load_settings({ENV[key]: ""}) == BUILT_IN
    in_file = ORDINARY[key][0]
    settings = resolve(["--config", config_file({key: in_file})], {ENV[key]: ""})
    assert settings[key] == in_file
    assert others_are_default(settings, key)


# --- flags: two arguments ----------------------------------------------------------------------


@pytest.mark.parametrize("value", ["-x", "--", "->"])
def test_flag_value_starting_with_dash(value):
    settings = resolve(["--prefix", value], {"APP_PREFIX": "job"})
    assert settings == {"timeout": 30, "retries": 3, "prefix": value}


def test_dash_values_among_other_flags(config_file):
    path = config_file({"timeout": 5, "retries": 1, "prefix": "svc"})
    argv = ["--retries", "2", "--prefix", "-v", "--config", path, "--timeout", "-1"]
    assert resolve(argv, {}) == {"timeout": -1, "retries": 2, "prefix": "-v"}
    assert resolve(["--timeout=-1"], {}) == {"timeout": -1, "retries": 3, "prefix": "app"}


def test_two_argument_value_is_never_read_as_a_flag(config_file):
    assert resolve(["--prefix", "k=v"], {}) == {"timeout": 30, "retries": 3, "prefix": "k=v"}
    assert resolve(["--prefix", " "], {}) == {"timeout": 30, "retries": 3, "prefix": " "}
    settings = resolve(["--prefix", "--timeout=5"], {})
    assert settings == {"timeout": 30, "retries": 3, "prefix": "--timeout=5"}
    settings = resolve(["--prefix", "--retries", "--retries", "2"], {})
    assert settings == {"timeout": 30, "retries": 2, "prefix": "--retries"}
    looks_like_config = "--config=" + config_file({"timeout": 5})
    settings = resolve(["--prefix", looks_like_config], {})
    assert settings == {"timeout": 30, "retries": 3, "prefix": looks_like_config}


# --- flags: one argument -----------------------------------------------------------------------


def test_one_argument_value_is_everything_after_the_first_equals(config_file):
    assert resolve(["--prefix=a=b"], {}) == {"timeout": 30, "retries": 3, "prefix": "a=b"}
    assert resolve(["--prefix==", "--timeout=5"], {}) == {"timeout": 5, "retries": 3, "prefix": "="}
    path = config_file({"retries": 1}, name="a=b.json")
    assert resolve([f"--config={path}"], {}) == {"timeout": 30, "retries": 1, "prefix": "app"}


def test_one_argument_value_may_be_empty(config_file):
    path = config_file({"prefix": "svc"})
    settings = resolve(["--config", path, "--prefix="], {"APP_PREFIX": "job"})
    assert settings == {"timeout": 30, "retries": 3, "prefix": ""}
    settings = resolve(["--prefix=", "--retries", "7"], {})
    assert settings == {"timeout": 30, "retries": 7, "prefix": ""}


# --- flags given more than once ----------------------------------------------------------------


def test_last_of_a_repeated_flag_counts(config_file):
    assert resolve(["--timeout", "5", "--timeout", "60"], {})["timeout"] == 60
    settings = resolve(["--prefix", "-x", "--prefix=-y"], {})
    assert settings == {"timeout": 30, "retries": 3, "prefix": "-y"}
    settings = resolve(["--retries=9", "--retries", "0"], {"APP_RETRIES": "7"})
    assert settings == {"timeout": 30, "retries": 0, "prefix": "app"}
    first = config_file({"timeout": 5, "prefix": "svc"}, name="first.json")
    second = config_file({"retries": 1}, name="second.json")
    settings = resolve(["--config", first, f"--config={second}"], {})
    assert settings == {"timeout": 30, "retries": 1, "prefix": "app"}


# --- nothing that is passed in, and not DEFAULTS, is modified ----------------------------------


def test_no_call_modifies_defaults_argv_or_environ(config_file):
    path = config_file({"timeout": 5, "retries": 0, "prefix": "svc"})
    argv = ["--config", path, "--prefix=web", "--timeout", "-1"]
    environ = {"APP_TIMEOUT": "60", "APP_RETRIES": ""}
    assert resolve(argv, environ) == {"timeout": -1, "retries": 0, "prefix": "web"}
    assert load_settings(environ, path) == {"timeout": 60, "retries": 0, "prefix": "svc"}
    assert argv == ["--config", path, "--prefix=web", "--timeout", "-1"]
    assert environ == {"APP_TIMEOUT": "60", "APP_RETRIES": ""}
    assert defaults.DEFAULTS == BUILT_IN
    assert resolve([], {}) == BUILT_IN


def test_returned_dict_is_new_on_every_call():
    settings = load_settings({})
    settings["retries"] = 9
    assert defaults.DEFAULTS == BUILT_IN
    assert load_settings({}) == BUILT_IN
    settings = resolve([], {})
    settings["prefix"] = "changed"
    assert defaults.DEFAULTS == BUILT_IN
    assert resolve([], {}) == BUILT_IN
    assert load_settings({}) is not load_settings({})
    assert resolve([], {}) is not resolve([], {})
