#!/bin/bash
# Plausible careless solution: the habitual shape, written once and checked only with the example
# test. It reads the clock once per call and gets every single-key rule right, but:
# - the purge helper collects expired entries in the order the OrderedDict holds them, which is
#   recency order, so pop_expired is not ordered by expiry time once a get has reordered entries;
# - put_many stores pair by pair, so an unhashable key raises only after the earlier pairs of the
#   list have already been stored (and may already have evicted something).
cat > /app/ttl_cache.py <<'EOF'
from collections import OrderedDict


class Cache:
    """Least-recently-used cache whose entries also expire."""

    def __init__(self, capacity, ttl, clock):
        self.capacity = capacity
        self.ttl = ttl
        self.clock = clock
        self._items = OrderedDict()  # key -> (value, expires_at), least recently used first
        self._expired = []

    def _purge(self, now):
        for key in [k for k, (_, expires_at) in self._items.items() if expires_at <= now]:
            value, _ = self._items.pop(key)
            self._expired.append((key, value))

    def _store(self, key, value, now):
        if self.capacity <= 0:
            return
        if key in self._items:
            self._items.move_to_end(key)
        elif len(self._items) >= self.capacity:
            self._items.popitem(last=False)
        self._items[key] = (value, now + self.ttl)

    def get(self, key, default=None):
        self._purge(self.clock())
        if key not in self._items:
            return default
        self._items.move_to_end(key)
        return self._items[key][0]

    def put(self, key, value):
        now = self.clock()
        self._purge(now)
        self._store(key, value, now)

    def put_many(self, pairs):
        now = self.clock()
        self._purge(now)
        for key, value in pairs:
            self._store(key, value, now)

    def pop_expired(self):
        self._purge(self.clock())
        expired, self._expired = self._expired, []
        return expired

    def __len__(self):
        self._purge(self.clock())
        return len(self._items)
EOF
