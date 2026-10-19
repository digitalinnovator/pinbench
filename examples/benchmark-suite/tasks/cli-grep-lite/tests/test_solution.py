import os
import subprocess
import sys

import pytest

sys.path.insert(0, "/app")
SCRIPT = os.path.abspath("grep_lite.py")  # the tests run with /app as the working directory

A_TEXT = "foo one\nbar\nFoo two\n\nlast foo\n"
B_TEXT = "nothing here\nfoo in b"  # the final line has no newline
C_TEXT = "bar only\nbar again\n"
D_TEXT = "abc\na.c\nk[x]\n"
RAW = b"foo\rbar\nfoo end\r\nzzz\x0cfoo\n"  # three lines: only "\n" ends a line


@pytest.fixture
def files(tmp_path):
    paths = {}
    for name, text in (("a", A_TEXT), ("b", B_TEXT), ("c", C_TEXT), ("d", D_TEXT)):
        path = tmp_path / f"{name}.txt"
        path.write_bytes(text.encode("ascii"))
        paths[name] = str(path)
    paths["missing"] = str(tmp_path / "missing.txt")
    return paths


def grep(*args, stdin=""):
    return subprocess.run(
        [sys.executable, SCRIPT, *args], input=stdin, capture_output=True, text=True, timeout=30
    )


def grep_bytes(*args, stdin=b""):
    """Like grep(), but with bytes in and out so that nothing here translates newlines."""
    return subprocess.run(
        [sys.executable, SCRIPT, *args], input=stdin, capture_output=True, timeout=30
    )


def check(result, stdout, status):
    assert result.stdout == stdout
    assert result.returncode == status


def test_selected_lines(files):
    check(grep("foo", files["a"]), "foo one\nlast foo\n", 0)


def test_nothing_selected(files):
    check(grep("zzz", files["a"]), "", 1)


def test_ignore_case(files):
    check(grep("-i", "FOO", files["a"]), "foo one\nFoo two\nlast foo\n", 0)


def test_invert(files):
    check(grep("-v", "foo", files["a"]), "bar\nFoo two\n\n", 0)


def test_line_numbers(files):
    check(grep("-n", "foo", files["a"]), "1:foo one\n5:last foo\n", 0)


def test_count(files):
    check(grep("-c", "foo", files["a"]), "2\n", 0)


def test_count_of_zero(files):
    check(grep("-c", "zzz", files["a"]), "0\n", 1)


def test_count_with_invert(files):
    check(grep("-c", "-v", "foo", files["a"]), "3\n", 0)


def test_count_ignores_line_numbers(files):
    a, b = files["a"], files["b"]
    check(grep("-c", "-n", "foo", a), "2\n", 0)
    check(grep("-c", "-n", "foo", a, b), f"{a}:2\n{b}:1\n", 0)


def test_final_line_without_newline(files):
    check(grep("foo", files["b"]), "foo in b\n", 0)


def test_line_ends_only_at_newline(tmp_path):
    path = tmp_path / "raw.txt"
    path.write_bytes(RAW)
    check(grep_bytes("foo", str(path)), RAW, 0)
    check(grep_bytes("-c", "foo", str(path)), b"3\n", 0)
    check(grep_bytes("-n", "bar", str(path)), b"1:foo\rbar\n", 0)


def test_line_ends_only_at_newline_on_standard_input():
    check(grep_bytes("foo", stdin=b"a\rfoo\r\nb\n"), b"a\rfoo\r\n", 0)


@pytest.mark.parametrize(("pattern", "stdout"), [("a.c", "a.c\n"), ("[x", "k[x]\n")])
def test_pattern_is_a_fixed_string(files, pattern, stdout):
    check(grep(pattern, files["d"]), stdout, 0)


def test_standard_input_when_no_file():
    check(grep("foo", stdin="x\nfoo y\n"), "foo y\n", 0)


def test_dash_is_standard_input():
    check(grep("-n", "foo", "-", stdin="x\nfoo y\n"), "2:foo y\n", 0)


def test_several_files(files):
    a, b = files["a"], files["b"]
    check(grep("foo", a, b), f"{a}:foo one\n{a}:last foo\n{b}:foo in b\n", 0)


def test_several_files_with_line_numbers(files):
    a, b = files["a"], files["b"]
    check(grep("-n", "foo", a, b), f"{a}:1:foo one\n{a}:5:last foo\n{b}:2:foo in b\n", 0)


def test_several_files_with_count(files):
    a, b, c = files["a"], files["b"], files["c"]
    check(grep("-c", "foo", a, c, b), f"{a}:2\n{c}:0\n{b}:1\n", 0)


def test_dash_among_several_files(files):
    a = files["a"]
    result = grep("foo", a, "-", stdin="foo z\n")
    check(result, f"{a}:foo one\n{a}:last foo\n-:foo z\n", 0)


def test_quiet_with_a_selected_line(files):
    check(grep("-q", "foo", files["a"]), "", 0)


def test_quiet_with_count(files):
    check(grep("-q", "-c", "foo", files["a"]), "", 0)


def test_unreadable_file(files):
    result = grep("foo", files["missing"])
    check(result, "", 2)
    assert result.stderr != ""


def test_unreadable_file_before_a_readable_one(files):
    a = files["a"]
    check(grep("foo", files["missing"], a), f"{a}:foo one\n{a}:last foo\n", 2)


def test_quiet_with_unreadable_file_after_a_readable_one(files):
    check(grep("-q", "foo", files["a"], files["missing"]), "", 2)
