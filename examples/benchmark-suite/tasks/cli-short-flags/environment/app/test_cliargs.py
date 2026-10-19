from cliargs import parse_argv

SPEC = {"v": False, "o": True, "color": False, "out": True}


def test_mixed_options_and_positionals():
    argv = ["-v", "--out", "x", "file.txt"]
    assert parse_argv(argv, SPEC) == ({"v": True, "out": "x"}, ["file.txt"])
