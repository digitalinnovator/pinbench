Refactor `/app/handlers.py` and `/app/loader.py`: the handler registry becomes a class instead of
one module-level dict. `/app/test_handlers.py` is a small smoke test for the result.

In `handlers.py`:

- Add a class `Registry`. Its methods `register(name, func=None)`, `get(name)` and `names()`
  behave as the module-level functions of those names do now, except as stated below.
- `Registry(capacity=None)` starts empty and never holds more than `capacity` handlers (an
  integer, 0 or more; `None` means no limit). No two instances share state.
- A valid name is a `str` of 1 to 32 characters, each one of `a`-`z`, `0`-`9`, `-` and `_`, the
  first one a letter. Every other value is an invalid name.
- `register` raises `ValueError` and changes nothing when the name is invalid, when it is
  already taken, or when the registry is full. It works as a direct call and as a decorator,
  and both forms return the function itself. In the decorator form `register(name)` makes these
  checks itself, and the decorator it returns makes them again when it is applied.
- `get` of a name that is not registered raises `KeyError`. `names()` returns a new sorted list.
- `len(registry)` is the number of handlers; `name in registry` tells whether a name is taken;
  iterating a registry yields its names in the same order as `names()`.
- `default_registry` is a module attribute holding a `Registry()` created at import time; other
  code may rebind it, and the default registry is always the current value of
  `handlers.default_registry`. The module-level `register`, `get` and `names` pass every call
  on to the method of the same name of whatever it currently holds.

In `loader.py`:

- `load_builtins(registry=None)` registers the three built-ins (`upper`, `lower`, `reverse`,
  behaving as now) in `registry`, or in the default registry when `registry` is `None`.
- It registers all three or none: if any of them cannot be registered, it raises `ValueError`
  and leaves the registry exactly as it was.
- As now, nothing is registered until `load_builtins` is called.
