from ttl_cache import Cache


def test_put_get_and_expire():
    now = [0]
    cache = Cache(2, 10, lambda: now[0])
    cache.put("a", 1)
    assert cache.get("a") == 1
    assert cache.get("missing", "fallback") == "fallback"
    now[0] = 10
    assert cache.pop_expired() == [("a", 1)]
