import sys

import pytest

sys.path.insert(0, "/app")
from cliargs import parse_argv  # noqa: E402

SPEC = {
    "v": False,
    "q": False,
    "o": True,
    "n": True,
    "color": False,
    "verbose": False,
    "no-verify": False,
    "no-cache": True,
    "key": True,
    "out": True,
    "output": True,
}

# Two long names share the prefix "no-ver", and two share the prefix "co".
SHARED = {
    "verbose": False,
    "no-verify": False,
    "no-version": False,
    "color": False,
    "config": True,
}


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (
            ["a", "-", "-v", "b", "--color", "c", "--", "-q", "--", "--key"],
            ({"v": True, "color": True}, ["a", "-", "b", "c", "-q", "--", "--key"]),
        ),
        (["--ke=", "x", "-o=x"], ({"key": "", "o": "x"}, ["x"])),
        (["-qofile", "x", "-nvq"], ({"q": True, "o": "file", "n": "vq"}, ["x"])),
        (["-o", "--", "--key", "-v"], ({"o": "--", "key": "-v"}, [])),
        (
            ["--verb", "--output=a=b", "--ke", "y"],
            ({"verbose": True, "output": "a=b", "key": "y"}, []),
        ),
        (["--out", "x", "--no-col"], ({"out": "x", "color": False}, [])),
        # A negative number is a positional, unless it is consumed as a value.
        (["-12", "-n", "-5", "-0.25", "-v"], ({"n": "-5", "v": True}, ["-12", "-0.25"])),
        # The name after "--" is looked up as a long name before it is read as "--no-name".
        (["--no-ver", "--no-ca=y"], ({"no-verify": True, "no-cache": "y"}, [])),
        (["--no-verify", "--no-cache", "x"], ({"no-verify": True, "no-cache": "x"}, [])),
        (["--no-verb", "--no-no-verify"], ({"verbose": False, "no-verify": False}, [])),
        # One leading "=" is dropped from a short option's value; the value may then be empty.
        (["-o=", "x"], ({"o": ""}, ["x"])),
        (["-vn==a"], ({"v": True, "n": "=a"}, [])),
    ],
)
def test_parse(argv, expected):
    options, positionals = parse_argv(argv, SPEC)
    assert (options, positionals) == expected


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["-v", "--key=a", "-q", "-v", "--key", "b"], [("q", True), ("v", True), ("key", "b")]),
        (["--color", "-n1", "--no-color"], [("n", "1"), ("color", False)]),
        (["-o", "a", "--out", "b", "-o", "c"], [("out", "b"), ("o", "c")]),
    ],
)
def test_keys_follow_last_occurrence(argv, expected):
    options, positionals = parse_argv(argv, SPEC)
    assert list(options.items()) == expected
    assert positionals == []


def test_inputs_are_not_modified():
    argv = ["-v", "--key", "x", "a", "--", "b"]
    spec = dict(SPEC)
    parse_argv(argv, spec)
    assert argv == ["-v", "--key", "x", "a", "--", "b"]
    assert spec == SPEC


@pytest.mark.parametrize(
    "argv",
    [
        ["-vz"],
        ["--q"],
        ["--c"],
        ["--ou=x"],
        ["--no-q"],
        ["--no-ke"],
        ["--col="],
        ["--no-color=x"],
        ["a", "--key"],
        ["-vo"],
        ["-.5"],
        ["-5."],
    ],
)
def test_errors(argv):
    with pytest.raises(ValueError):
        parse_argv(argv, SPEC)


@pytest.mark.parametrize("argv", [["--no-ver"], ["--no-co"]])
def test_prefix_of_more_than_one_long_name(argv):
    with pytest.raises(ValueError):
        parse_argv(argv, SHARED)
