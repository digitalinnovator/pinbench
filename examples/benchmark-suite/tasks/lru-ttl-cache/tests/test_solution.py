import sys

import pytest

sys.path.insert(0, "/app")
from ttl_cache import Cache  # noqa: E402

START = 100


class Clock:
    """Injected time source. `at(n)` moves it to n time units after the start."""

    def __init__(self):
        self.now = START
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.now

    def at(self, offset):
        self.now = START + offset


def make(capacity, ttl=10):
    clock = Clock()
    return Cache(capacity, ttl, clock), clock


def clock_calls(clock, operation):
    """How many times `operation` read the clock."""
    before = clock.calls
    operation()
    return clock.calls - before


# --- get, put and len without expiry -------------------------------------------------------


def test_get_returns_stored_value_or_default():
    cache, _ = make(3)
    assert len(cache) == 0
    assert cache.put("a", 1) is None
    assert cache.put("a", 2) is None
    assert cache.get("a") == 2
    assert cache.get("nope") is None
    assert cache.get("nope", "fallback") == "fallback"
    cache.put("none", None)
    cache.put("zero", 0)
    assert cache.get("none", "fallback") is None  # a stored value wins over the default
    assert cache.get("zero", "fallback") == 0
    assert len(cache) == 3


# --- least-recently-used eviction ----------------------------------------------------------


def test_evicts_least_recently_used():
    cache, _ = make(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert len(cache) == 2


def test_get_makes_entry_most_recently_used():
    cache, _ = make(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_capacity_zero_stores_nothing():
    cache, clock = make(0)
    cache.put("a", 1)
    cache.put_many([("b", 2), ("c", 3)])
    assert cache.get("a") is None
    assert cache.get("b", "fallback") == "fallback"
    assert len(cache) == 0
    clock.at(30)
    assert cache.pop_expired() == []


# --- put on a live key ---------------------------------------------------------------------


def test_put_on_live_key_replaces_value_and_evicts_nothing():
    cache, _ = make(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("b", 9)
    assert len(cache) == 2
    assert cache.get("a") == 1
    assert cache.get("b") == 9


def test_put_on_live_key_restarts_ttl():
    cache, clock = make(2)
    cache.put("a", 1)
    clock.at(6)
    cache.put("a", 2)
    clock.at(13)
    assert cache.get("a") == 2
    clock.at(18)
    assert cache.get("a") is None


def test_put_on_live_key_makes_it_most_recently_used():
    cache, _ = make(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 3)
    cache.put("c", 4)
    assert cache.get("b") is None
    assert cache.get("a") == 3
    assert cache.get("c") == 4


# --- expiry --------------------------------------------------------------------------------


def test_entry_expires_once_its_ttl_has_fully_elapsed():
    for offset, expected in [(9, 1), (10, "fallback"), (12, "fallback")]:
        cache, clock = make(2)
        cache.put("a", 1)
        clock.at(offset)
        assert cache.get("a", "fallback") == expected


def test_get_does_not_postpone_expiry():
    cache, clock = make(2)
    cache.put("a", 1)
    clock.at(8)
    assert cache.get("a") == 1
    clock.at(12)
    assert cache.get("a") is None


def test_len_counts_only_live_entries():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(5)
    cache.put("b", 2)
    clock.at(12)
    assert len(cache) == 1
    clock.at(20)
    assert len(cache) == 0


def test_put_on_expired_key_stores_a_fresh_entry():
    cache, clock = make(2)
    cache.put("a", "old")
    clock.at(5)
    cache.put("b", 2)
    clock.at(12)
    cache.put("a", "new")
    assert cache.get("a") == "new"
    assert cache.get("b") == 2
    clock.at(21)
    assert cache.get("a") == "new"
    clock.at(23)
    assert cache.get("a") is None


# --- expiry and capacity together ----------------------------------------------------------


def test_expired_entry_does_not_count_towards_capacity():
    cache, clock = make(2)
    cache.put("a", 1)
    clock.at(5)
    cache.put("b", 2)
    clock.at(12)
    cache.put("c", 3)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert len(cache) == 2


def test_expired_entry_goes_before_a_less_recently_used_live_one():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(4)
    cache.put("b", 2)
    clock.at(8)
    cache.put("c", 3)
    clock.at(9)
    assert cache.get("a") == 1  # "b" is now the least recently used
    clock.at(12)  # "a" has expired, "b" and "c" are live
    cache.put("d", 4)
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert cache.get("d") == 4
    assert len(cache) == 3


def test_entry_at_exactly_its_ttl_is_not_counted_by_len_or_capacity():
    cache, clock = make(2)
    cache.put("a", 1)
    clock.at(5)
    cache.put("b", 2)
    clock.at(6)
    assert cache.get("a") == 1  # "b" is now the least recently used
    clock.at(10)
    assert len(cache) == 1
    cache.put("c", 3)
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert cache.get("a") is None


def test_mixed_sequence():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(2)
    cache.put("b", 2)
    clock.at(4)
    cache.put("c", 3)
    clock.at(5)
    assert cache.get("a") == 1
    clock.at(6)
    cache.put("d", 4)  # full of live entries: "b" is the least recently used
    assert cache.get("b") is None
    clock.at(11)
    cache.put("e", 5)  # "a" has expired, so no live entry has to go
    clock.at(12)
    assert cache.get("c") == 3
    clock.at(13)
    cache.put("f", 6)  # live: "d", "e", "c" in recency order
    assert cache.get("d") is None
    assert cache.get("e") == 5
    assert cache.get("c") == 3
    assert cache.get("f") == 6
    assert cache.get("a") is None


# --- put_many ------------------------------------------------------------------------------


def test_put_many_stores_the_pairs_in_list_order_as_put_would():
    cache, _ = make(2)
    assert cache.put_many([("a", 1), ("b", 2), ("c", 3)]) is None
    assert len(cache) == 2  # "a" was the least recently used when "c" arrived
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_put_many_with_a_repeated_key_keeps_the_later_pair_and_its_recency():
    cache, _ = make(2)
    cache.put_many([("a", 1), ("b", 2), ("a", 3)])
    assert len(cache) == 2
    cache.put("c", 4)  # "b" is the least recently used: "a" was written again after it
    assert cache.get("b") is None
    assert cache.get("a") == 3
    assert cache.get("c") == 4


def test_put_many_stores_every_pair_at_the_current_clock_time():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(6)
    cache.put_many([("a", 2), ("b", 3)])  # "a" is live: its ttl restarts
    clock.at(13)
    assert cache.get("a") == 2
    assert cache.get("b") == 3
    clock.at(16)
    assert cache.get("a") is None
    assert cache.get("b") is None
    assert len(cache) == 0


def test_put_many_with_an_unhashable_key_stores_and_evicts_nothing():
    cache, _ = make(2)
    cache.put("a", 1)
    cache.put("b", 2)
    with pytest.raises(TypeError):
        cache.put_many([("a", 9), ("c", 3), (["x"], 4), ("d", 5)])
    assert len(cache) == 2
    assert cache.get("c") is None
    assert cache.get("d") is None
    assert cache.get("b") == 2
    assert cache.get("a") == 1


def test_put_many_with_an_unhashable_key_keeps_the_recency_order():
    cache, _ = make(2)
    cache.put("a", 1)
    cache.put("b", 2)
    with pytest.raises(TypeError):
        cache.put_many([("a", 1), ({}, 0)])
    cache.put("c", 3)  # "a" is still the least recently used
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_put_many_with_an_unhashable_key_keeps_the_expiry_times():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(6)
    with pytest.raises(TypeError):
        cache.put_many([("a", 1), (["x"], 0)])
    clock.at(9)
    assert cache.get("a") == 1
    clock.at(11)  # "a" was stored at 0, so it expired at 10
    assert cache.get("a") is None


def test_put_many_with_an_unhashable_key_does_not_change_what_pop_expired_returns():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(12)  # "a" expired at 10
    with pytest.raises(TypeError):
        cache.put_many([("b", 2), (["x"], 0)])
    assert cache.pop_expired() == [("a", 1)]
    clock.at(40)
    assert len(cache) == 0
    assert cache.pop_expired() == []


# --- pop_expired ---------------------------------------------------------------------------


def test_pop_expired_returns_each_expired_entry_once():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(5)
    cache.put("k", None)
    clock.at(9)
    assert cache.pop_expired() == []
    clock.at(10)
    assert cache.get("a") is None  # "a" expires at exactly 10
    assert cache.pop_expired() == [("a", 1)]
    assert cache.pop_expired() == []
    clock.at(15)
    assert len(cache) == 0
    assert cache.pop_expired() == [("k", None)]
    assert cache.pop_expired() == []


def test_pop_expired_is_ordered_by_expiry_time():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(1)
    cache.put("b", 2)
    clock.at(2)
    cache.put("c", 3)
    clock.at(3)
    assert cache.get("a") == 1
    clock.at(4)
    assert cache.get("b") == 2
    clock.at(20)  # expiry times: "a" 10, "b" 11, "c" 12
    assert cache.pop_expired() == [("a", 1), ("b", 2), ("c", 3)]


def test_pop_expired_is_ordered_by_expiry_time_when_another_call_saw_the_expiry_first():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(2)
    cache.put("b", 2)
    clock.at(3)
    assert cache.get("a") == 1
    clock.at(15)  # "a" expired at 10 and "b" at 12
    cache.put("c", 3)
    assert len(cache) == 1
    clock.at(40)
    assert cache.pop_expired() == [("a", 1), ("b", 2), ("c", 3)]


def test_pop_expired_order_follows_a_restarted_ttl():
    cache, clock = make(3)
    cache.put("a", 1)
    clock.at(1)
    cache.put("b", 2)
    clock.at(2)
    cache.put("a", 3)  # live key: "a" now expires at 12, after "b" at 11
    clock.at(20)
    assert cache.pop_expired() == [("b", 2), ("a", 3)]


def test_pop_expired_leaves_out_evicted_entries_and_replaced_values():
    cache, clock = make(2)
    cache.put("a", 1)
    clock.at(1)
    cache.put("b", 2)
    clock.at(2)
    cache.put("a", 3)  # live key: 1 is replaced, "a" now expires at 12
    clock.at(3)
    cache.put("c", 4)  # full: "b" is evicted
    clock.at(12)
    cache.put("d", 5)  # "a" has expired, so nothing is evicted
    assert cache.pop_expired() == [("a", 3)]
    assert len(cache) == 2
    clock.at(30)
    assert cache.pop_expired() == [("c", 4), ("d", 5)]


def test_pop_expired_reports_an_expired_entry_whose_key_was_put_again():
    cache, clock = make(2)
    cache.put("a", "old")
    clock.at(12)
    cache.put("a", "new")  # "old" expired at 10: this is a new entry, expiring at 22
    assert cache.get("a") == "new"
    clock.at(30)
    assert cache.pop_expired() == [("a", "old"), ("a", "new")]


# --- how often the clock is read -----------------------------------------------------------


def test_get_put_and_len_call_the_clock_at_most_once():
    cache, clock = make(2)
    assert clock_calls(clock, lambda: cache.put("a", 1)) <= 1
    cache.put("b", 2)
    assert clock_calls(clock, lambda: cache.put("c", 3)) <= 1  # full: a live entry is evicted
    assert clock_calls(clock, lambda: cache.put("c", 4)) <= 1  # live key
    clock.at(5)
    cache.put("d", 5)
    clock.at(12)  # "c" has expired, "d" is live
    for key in ("d", "c", "nope"):
        assert clock_calls(clock, lambda: cache.get(key)) <= 1
    assert clock_calls(clock, lambda: len(cache)) <= 1
    assert clock_calls(clock, lambda: cache.put("e", 6)) <= 1  # an expired entry is present


def test_put_many_and_pop_expired_call_the_clock_at_most_once():
    cache, clock = make(3)
    assert clock_calls(clock, lambda: cache.put_many([("a", 1), ("b", 2), ("c", 3)])) <= 1
    clock.at(4)
    assert clock_calls(clock, lambda: cache.put_many([("c", 4), ("d", 5)])) <= 1  # "a" is evicted
    clock.at(12)  # "b" has expired, "c" and "d" are live
    assert clock_calls(clock, lambda: cache.pop_expired()) <= 1
    clock.at(30)
    assert clock_calls(clock, lambda: cache.pop_expired()) <= 1
