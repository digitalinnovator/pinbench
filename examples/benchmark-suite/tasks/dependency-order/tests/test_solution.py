import copy
import sys

import pytest

sys.path.insert(0, "/app")
from deps import CycleError, install_order, remove_order  # noqa: E402

MIXED = {"web": ["db", "cache"], "db": ["core"], "cache": [], "api": ["zlib"], "zlib": []}
REPEATED = {"app": ["lib", "core", "lib"], "lib": ["core", "core"]}

INSTALL_CASES = {
    "empty": ({}, []),
    "unlisted_dependency": ({"app": ["lib"]}, ["lib", "app"]),
    "repeated_dependency": (REPEATED, ["core", "lib", "app"]),
    "str_comparison": ({"b": [], "B": [], "a10": [], "a2": []}, ["B", "a10", "a2", "b"]),
    "freed_package_goes_next": ({"b": ["a"], "c": [], "a": []}, ["a", "b", "c"]),
    "smallest_ready_first": ({"a": ["c"], "b": [], "c": []}, ["b", "c", "a"]),
    "mixed": (MIXED, ["cache", "core", "db", "web", "zlib", "api"]),
}

REMOVE_CASES = {
    "empty": ({}, []),
    "independent": ({"pear": [], "apple": [], "fig": []}, ["apple", "fig", "pear"]),
    "unlisted_dependency": ({"app": ["lib"]}, ["app", "lib"]),
    "repeated_dependency": (REPEATED, ["app", "lib", "core"]),
    "freed_package_goes_next": ({"a": ["b"], "c": []}, ["a", "b", "c"]),
    "mixed": (MIXED, ["api", "web", "cache", "db", "core", "zlib"]),
}

# Each entry: the dependencies and the one cycle that both functions must report.
CYCLE_CASES = {
    "three": ({"a": ["c"], "c": ["b"], "b": ["a"]}, ["a", "c", "b"]),
    "self_among_others": ({"app": ["lib"], "lib": ["lib", "core"], "core": []}, ["lib"]),
    "reached_from_outside": (
        {"a": ["t"], "t": ["m"], "m": ["k"], "k": ["t"]},
        ["k", "t", "m"],
    ),
    "members_with_other_dependencies": (
        {"p": ["r", "base"], "r": ["q", "q", "extra"], "q": ["p"], "base": [], "z": ["base"]},
        ["p", "r", "q"],
    ),
    "smallest_member_of_any_cycle": (
        {"a": ["b"], "b": ["c", "z"], "c": ["b"], "z": ["a"]},
        ["a", "b", "z"],
    ),
    "separate_cycles": (
        {"a": ["x"], "x": ["y"], "y": ["x"], "c": ["d"], "d": ["c"]},
        ["c", "d"],
    ),
    "package_between_two_cycles": (
        {"k": ["l"], "l": ["k", "b"], "b": ["m"], "m": ["n"], "n": ["m"]},
        ["k", "l"],
    ),
    "fewest_packages": ({"a": ["b", "c"], "b": ["c"], "c": ["a"]}, ["a", "c"]),
    "fewest_packages_among_many": (
        {
            "a": ["b", "c", "d", "e", "z"],
            "b": ["b2"],
            "c": ["c2"],
            "d": ["d2"],
            "e": ["e2"],
            "b2": ["a"],
            "c2": ["a"],
            "d2": ["a"],
            "e2": ["a"],
            "z": ["a"],
        },
        ["a", "z"],
    ),
    "same_size_differs_at_second": (
        {"a": ["g", "f", "e", "d", "c", "b"]} | {name: ["a"] for name in "bcdefg"},
        ["a", "b"],
    ),
    "same_size_differs_in_the_middle": (
        {"a": ["e", "d", "c", "b"], "b": ["z"], "c": ["y"], "d": ["x"], "e": ["w"]}
        | {name: ["a"] for name in "wxyz"},
        ["a", "b", "z"],
    ),
    "same_size_differs_at_last": (
        {"a": ["b"], "b": ["g", "f", "e", "d", "c"]} | {name: ["a"] for name in "cdefg"},
        ["a", "b", "c"],
    ),
    "same_size_shared_last_package": (
        {"a": ["e", "d", "c", "b"], "m": ["a"]} | {name: ["m"] for name in "bcde"},
        ["a", "b", "m"],
    ),
}

LONG = [f"p{number:04d}" for number in range(2000)]
LONG_CHAIN = {name: [following] for name, following in zip(LONG, LONG[1:])}
LONG_CYCLE = {name: [following] for name, following in zip(LONG, LONG[1:] + LONG[:1])}


def cycle_of(function, deps):
    with pytest.raises(CycleError) as excinfo:
        function(deps)
    return excinfo.value.cycle


@pytest.mark.parametrize(("deps", "expected"), INSTALL_CASES.values(), ids=INSTALL_CASES.keys())
def test_install_order(deps, expected):
    assert install_order(deps) == expected


@pytest.mark.parametrize(("deps", "expected"), REMOVE_CASES.values(), ids=REMOVE_CASES.keys())
def test_remove_order(deps, expected):
    assert remove_order(deps) == expected


@pytest.mark.parametrize(("deps", "expected"), CYCLE_CASES.values(), ids=CYCLE_CASES.keys())
def test_cycle(deps, expected):
    assert cycle_of(install_order, deps) == expected
    assert cycle_of(remove_order, deps) == expected


def test_chain_of_2000_packages():
    assert install_order(LONG_CHAIN) == LONG[::-1]
    assert remove_order(LONG_CHAIN) == LONG


def test_cycle_of_2000_packages():
    assert cycle_of(install_order, LONG_CYCLE) == LONG
    assert cycle_of(remove_order, LONG_CYCLE) == LONG


def test_input_is_not_modified():
    deps = {"app": ["lib", "core", "lib"], "lib": ["core"]}
    before = copy.deepcopy(deps)
    install_order(deps)
    remove_order(deps)
    assert deps == before


def test_input_is_not_modified_when_there_is_a_cycle():
    deps = {"k": ["t"], "a": ["t", "m", "t"], "t": ["m"], "m": ["k"]}
    before = copy.deepcopy(deps)
    cycle_of(install_order, deps)
    cycle_of(remove_order, deps)
    assert deps == before
