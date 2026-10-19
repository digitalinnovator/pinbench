"""Registers the built-in handlers."""

from handlers import register


def upper(text):
    return text.upper()


def lower(text):
    return text.lower()


def load_builtins():
    register("upper", upper)
    register("lower", lower)

    @register("reverse")
    def reverse(text):
        return text[::-1]
