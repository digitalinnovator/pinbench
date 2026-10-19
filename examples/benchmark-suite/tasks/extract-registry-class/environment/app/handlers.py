"""Text handlers, looked up by name."""

_handlers = {}


def register(name, func=None):
    """Register func under name and return func.

    Call it directly, register("upper", str.upper), or use it as a decorator,
    @register("upper").
    """
    if func is None:
        return lambda f: register(name, f)
    if name in _handlers:
        raise ValueError(f"handler already registered: {name}")
    _handlers[name] = func
    return func


def get(name):
    """Return the handler registered under name; KeyError if there is none."""
    return _handlers[name]


def names():
    """Return the registered names as a new sorted list."""
    return sorted(_handlers)
