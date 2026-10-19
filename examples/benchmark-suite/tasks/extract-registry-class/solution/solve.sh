#!/bin/bash
cat > /app/handlers.py <<'EOF'
"""Text handlers, looked up by name."""

import re

# One lowercase ASCII letter, then up to 31 more of a-z, 0-9, "-" and "_". Used with fullmatch.
_NAME = re.compile(r"[a-z][a-z0-9_-]{0,31}")


class Registry:
    """A set of named handlers. Every instance owns its own mapping."""

    def __init__(self, capacity=None):
        self._capacity = capacity
        self._handlers = {}

    def _check(self, name, handlers):
        """Raise ValueError unless name could be added to the mapping handlers."""
        # isinstance first: a name that is not a str is invalid, not a TypeError.
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            raise ValueError(f"invalid handler name: {name!r}")
        if name in handlers:
            raise ValueError(f"handler already registered: {name}")
        # "is not None", not truthiness: a capacity of 0 is a limit too.
        if self._capacity is not None and len(handlers) >= self._capacity:
            raise ValueError(f"registry is full: {self._capacity} handlers")

    def register(self, name, func=None):
        """Register func under name and return func.

        Call it directly, registry.register("upper", str.upper), or use it as a
        decorator, @registry.register("upper"). The checks run before the
        decorator is handed out, and again when it is applied.
        """
        self._check(name, self._handlers)
        if func is None:
            return lambda f: self.register(name, f)
        self._handlers[name] = func
        return func

    def _register_all(self, handlers):
        """Register every (name, func) of the mapping handlers, or none of them.

        Private on purpose: the task asks for no public method beyond register, get and names.
        """
        staged = dict(self._handlers)
        for name, func in handlers.items():
            self._check(name, staged)
            staged[name] = func
        self._handlers = staged

    def get(self, name):
        """Return the handler registered under name; KeyError if there is none."""
        return self._handlers[name]

    def names(self):
        """Return the registered names as a new sorted list."""
        return sorted(self._handlers)

    def __len__(self):
        return len(self._handlers)

    def __contains__(self, name):
        return name in self._handlers

    def __iter__(self):
        # Same order as names(): sorted, not the dict's insertion order.
        return iter(sorted(self._handlers))


default_registry = Registry()


# The wrappers read the module global on every call, so rebinding
# handlers.default_registry redirects them.
def register(name, func=None):
    return default_registry.register(name, func)


def get(name):
    return default_registry.get(name)


def names():
    return default_registry.names()
EOF
cat > /app/loader.py <<'EOF'
"""Registers the built-in handlers."""

import handlers


def upper(text):
    return text.upper()


def lower(text):
    return text.lower()


def reverse(text):
    return text[::-1]


_BUILTINS = {"upper": upper, "lower": lower, "reverse": reverse}


def load_builtins(registry=None):
    # "is None", not truthiness: an empty Registry has len() == 0 and is falsy.
    # handlers.default_registry is read here, at call time, so a rebound default is honoured.
    if registry is None:
        registry = handlers.default_registry
    # All three or none, whatever the reason: a taken name or too little room. The public
    # register() adds one handler at a time and cannot be undone, so the registry stages the
    # three itself and swaps them in only when every check has passed.
    registry._register_all(_BUILTINS)
EOF
