import sys

import pytest

sys.path.insert(0, "/app")
import handlers  # noqa: E402
import loader  # noqa: E402
from handlers import Registry  # noqa: E402

# Every test below passes on its own and in any order. The tests that use the registry created at
# import time only add names no other test uses, and the one load_builtins() call on it is made
# by a module-scoped fixture, so it happens once whichever test asks for it first.
NAMES_AT_IMPORT = list(handlers.names())
DEFAULT_AT_IMPORT = handlers.default_registry
BUILTINS = ["lower", "reverse", "upper"]


def shout(text):
    return text.upper() + "!"


def whisper(text):
    return text.lower() + "..."


@pytest.fixture
def loaded():
    """A registry holding one custom handler plus the built-ins."""
    registry = Registry()
    registry.register("shout", shout)
    loader.load_builtins(registry)
    return registry


@pytest.fixture(scope="module")
def default_loaded():
    """load_builtins() called once, with no argument, on the registry created at import time."""
    loader.load_builtins()


# --- the default registry and the loader -------------------------------------------------


def test_nothing_is_registered_at_import():
    assert NAMES_AT_IMPORT == []
    assert isinstance(DEFAULT_AT_IMPORT, Registry)


def test_load_builtins_without_argument_fills_the_default_registry(default_loaded):
    assert set(BUILTINS) <= set(handlers.names())
    assert set(BUILTINS) <= set(handlers.default_registry.names())
    assert handlers.get("upper")("abc") == "ABC"


def test_builtins_behave_as_before_in_a_given_registry(loaded):
    assert loaded.names() == ["lower", "reverse", "shout", "upper"]
    assert len(loaded) == 4
    assert loaded.get("upper")("aBc") == "ABC"
    assert loaded.get("lower")("aBc") == "abc"
    assert loaded.get("reverse")("aBc") == "cBa"
    assert loaded.get("shout") is shout


def test_load_builtins_fills_a_new_registry_and_leaves_the_default_alone():
    before = handlers.names()
    mine = Registry()
    loader.load_builtins(registry=mine)
    assert mine.names() == BUILTINS
    assert len(mine) == 3
    assert handlers.names() == before


def test_load_builtins_leaves_the_registry_unchanged_when_a_name_is_taken(loaded):
    for taken in BUILTINS:
        registry = Registry()
        registry.register(taken, shout)
        with pytest.raises(ValueError):
            loader.load_builtins(registry)
        assert registry.names() == [taken]
        assert registry.get(taken) is shout
    with pytest.raises(ValueError):
        loader.load_builtins(loaded)
    assert loaded.names() == ["lower", "reverse", "shout", "upper"]


@pytest.mark.parametrize(("capacity", "present"), [(2, []), (4, ["shout", "whisper"])])
def test_load_builtins_registers_nothing_without_room_for_all_three(capacity, present):
    registry = Registry(capacity=capacity)
    for name in present:
        registry.register(name, shout)
    with pytest.raises(ValueError):
        loader.load_builtins(registry)
    assert registry.names() == present
    assert len(registry) == len(present)


def test_load_builtins_fills_a_registry_with_exactly_enough_room():
    registry = Registry(capacity=4)
    registry.register("shout", shout)
    loader.load_builtins(registry)
    assert registry.names() == ["lower", "reverse", "shout", "upper"]
    with pytest.raises(ValueError):
        registry.register("whisper", whisper)
    assert len(registry) == 4


def test_module_functions_follow_a_reassigned_default(monkeypatch):
    fresh = Registry()
    monkeypatch.setattr(handlers, "default_registry", fresh)
    assert handlers.register("swapped", shout) is shout
    assert fresh.get("swapped") is shout
    assert handlers.get("swapped") is shout
    assert handlers.names() == ["swapped"]


def test_load_builtins_follows_a_reassigned_default(monkeypatch):
    fresh = Registry()
    monkeypatch.setattr(handlers, "default_registry", fresh)
    loader.load_builtins()
    assert fresh.names() == BUILTINS


# --- the Registry class ------------------------------------------------------------------


def test_new_registry_is_empty_and_supports_len_and_in():
    registry = Registry()
    assert registry.names() == []
    assert len(registry) == 0
    assert "shout" not in registry
    registry.register("shout", shout)
    registry.register("whisper", whisper)
    assert len(registry) == 2
    assert "shout" in registry
    assert "missing" not in registry


def test_both_forms_return_the_function_itself():
    registry = Registry()
    assert registry.register("shout", shout) is shout
    assert registry.get("shout") is shout

    def original(text):
        return text

    decorated = registry.register("same")(original)
    assert decorated is original
    assert registry.get("same") is original


def test_module_level_decorator_returns_the_function():
    @handlers.register("module-decorated")
    def echo(text):
        return text + text

    assert echo("ab") == "abab"
    assert handlers.get("module-decorated") is echo
    assert handlers.default_registry.get("module-decorated") is echo


def test_duplicate_registration_raises_and_changes_nothing():
    registry = Registry()
    registry.register("dup", shout)
    with pytest.raises(ValueError):
        registry.register("dup", whisper)
    assert registry.get("dup") is shout
    assert registry.names() == ["dup"]


def test_get_of_an_unregistered_name_raises_key_error():
    with pytest.raises(KeyError):
        Registry().get("missing")
    with pytest.raises(KeyError):
        handlers.get("never-registered")


def test_names_is_a_new_sorted_list_and_iteration_follows_it():
    registry = Registry()
    for name in ("pear", "apple", "fig"):
        registry.register(name, shout)
    listed = registry.names()
    assert listed == ["apple", "fig", "pear"]
    listed.append("zebra")
    assert registry.names() == ["apple", "fig", "pear"]
    assert list(registry) == ["apple", "fig", "pear"]


def test_registries_do_not_share_handlers():
    first, second = Registry(), Registry()

    @first.register("one")
    @second.register("two")
    def both(text):
        return text

    assert first.names() == ["one"]
    assert second.names() == ["two"]
    second.register("one", whisper)
    assert first.get("one") is both
    assert second.get("one") is whisper

    handlers.register("default-only", shout)
    assert "default-only" not in first
    assert "one" not in handlers.names()
    with pytest.raises(KeyError):
        handlers.get("one")


# --- names -------------------------------------------------------------------------------

VALID = ["a", "x9", "to-upper", "snake_case", "a-", "b_", "h2-_x", "a" * 32, "z" + "9" * 31]


def test_valid_names_are_accepted():
    registry = Registry()
    for name in VALID:
        assert registry.register(name, shout) is shout
    assert registry.names() == sorted(VALID)


def assert_rejected(name):
    registry = Registry()
    with pytest.raises(ValueError):
        registry.register(name, shout)
    assert registry.names() == []
    assert len(registry) == 0


def test_names_outside_the_rule_are_rejected():
    for name in ["Upper", "uPPer", "two words", "dot.ted", "upper ", " upper", "a/b", "x=1"]:
        assert_rejected(name)
    for name in ["upper\n", "up\nper", "upper\t"]:
        assert_rejected(name)
    for name in ["", "9lives", "-dash", "_private"]:
        assert_rejected(name)


def test_letters_and_digits_outside_the_listed_ones_are_rejected():
    for name in ["caf\u00e9", "\u00e9clair", "x\u0663", "a\u00b2"]:
        assert_rejected(name)


def test_a_name_of_33_characters_is_rejected():
    assert_rejected("a" * 33)


@pytest.mark.parametrize("name", [5, b"upper"], ids=["int", "bytes"])
def test_a_name_that_is_not_a_str_is_rejected(name):
    assert_rejected(name)


# --- when the checks are made ------------------------------------------------------------


@pytest.mark.parametrize(
    ("capacity", "name"),
    [(None, "shout"), (None, "Not Valid"), (1, "whisper")],
    ids=["taken", "invalid", "full"],
)
def test_register_without_a_function_makes_the_checks_itself(capacity, name):
    registry = Registry(capacity=capacity)
    registry.register("shout", shout)
    with pytest.raises(ValueError):
        registry.register(name)
    assert registry.names() == ["shout"]


def test_the_decorator_makes_the_checks_again_when_it_is_applied():
    registry = Registry()
    decorate = registry.register("late")
    registry.register("late", shout)
    with pytest.raises(ValueError):
        decorate(whisper)
    assert registry.get("late") is shout
    assert len(registry) == 1

    small = Registry(capacity=1)
    decorate = small.register("first")
    small.register("second", shout)
    with pytest.raises(ValueError):
        decorate(whisper)
    assert small.names() == ["second"]


def test_module_level_register_makes_the_checks_itself():
    handlers.register("wrapped-early", shout)
    with pytest.raises(ValueError):
        handlers.register("wrapped-early")
    with pytest.raises(ValueError):
        handlers.register("Not Valid")
    assert handlers.get("wrapped-early") is shout


# --- capacity ----------------------------------------------------------------------------


def test_capacity_limits_the_number_of_handlers():
    registry = Registry(capacity=2)
    registry.register("one", shout)
    registry.register("two", whisper)
    with pytest.raises(ValueError):
        registry.register("three", shout)
    assert registry.names() == ["one", "two"]
    assert "three" not in registry

    unlimited = Registry(capacity=None)
    for number in range(50):
        unlimited.register(f"h{number}", shout)
    assert len(unlimited) == 50


def test_a_capacity_of_zero_holds_nothing():
    registry = Registry(capacity=0)
    with pytest.raises(ValueError):
        registry.register("shout", shout)
    assert len(registry) == 0
    assert registry.names() == []
