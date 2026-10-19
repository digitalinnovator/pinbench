import handlers
import loader


def test_loader_fills_the_default_registry():
    loader.load_builtins()
    assert isinstance(handlers.default_registry, handlers.Registry)
    assert handlers.names() == ["lower", "reverse", "upper"]
    assert handlers.get("upper")("abc") == "ABC"
