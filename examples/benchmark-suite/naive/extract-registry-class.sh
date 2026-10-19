#!/bin/bash
# Plausible careless solution: the refactor works on the smoke test, but was done in a hurry.
#  - the old body of register() was moved into the class as it was, so the decorator form hands
#    out a decorator first and makes the checks only when that decorator is applied
#  - the name pattern is applied to whatever comes in: a name that is not a str raises TypeError
#  - the pattern ends in "$" and is used with match(), so a valid name followed by a newline is
#    accepted although a newline is not one of the allowed characters
#  - "if self.capacity and ..." treats a capacity of 0 as "no limit"
#  - load_builtins looks only for taken names up front, so a registry without room for all three
#    is left holding the first ones
cat > /app/handlers.py <<'EOF'
"""Text handlers, looked up by name."""

import re

_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class Registry:
    """A collection of named handlers."""

    def __init__(self, capacity=None):
        self.capacity = capacity
        self._handlers = {}

    def register(self, name, func=None):
        """Register func under name and return func.

        Call it directly, registry.register("upper", str.upper), or use it as a
        decorator, @registry.register("upper").
        """
        if func is None:
            return lambda f: self.register(name, f)
        if not _NAME_RE.match(name):
            raise ValueError(f"invalid handler name: {name!r}")
        if name in self._handlers:
            raise ValueError(f"handler already registered: {name}")
        if self.capacity and len(self._handlers) >= self.capacity:
            raise ValueError("registry is full")
        self._handlers[name] = func
        return func

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
        return iter(self.names())


default_registry = Registry()


def register(name, func=None):
    """Register func under name in the default registry and return func."""
    return default_registry.register(name, func)


def get(name):
    """Return the handler registered under name in the default registry."""
    return default_registry.get(name)


def names():
    """Return the default registry's registered names as a new sorted list."""
    return default_registry.names()
EOF
cat > /app/loader.py <<'EOF'
"""Registers the built-in handlers."""

import handlers


def upper(text):
    return text.upper()


def lower(text):
    return text.lower()


def load_builtins(registry=None):
    if registry is None:
        registry = handlers.default_registry

    for name in ("upper", "lower", "reverse"):
        if name in registry:
            raise ValueError(f"handler already registered: {name}")

    registry.register("upper", upper)
    registry.register("lower", lower)

    @registry.register("reverse")
    def reverse(text):
        return text[::-1]
EOF
