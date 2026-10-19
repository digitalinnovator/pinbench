#!/bin/bash
cat > /app/ttl_cache.py <<'EOF'
from collections import OrderedDict
from typing import Any, Callable


class Cache:
    """Least-recently-used cache whose entries also expire."""

    def __init__(self, capacity: int, ttl: float, clock: Callable[[], float]) -> None:
        self._capacity = capacity
        self._ttl = ttl
        self._clock = clock
        # key -> (value, expiry time), ordered from least to most recently used.
        self._entries: OrderedDict[Any, tuple[Any, float]] = OrderedDict()
        # Expired entries that pop_expired has not handed out yet, earliest expiry first.
        self._expired: list[tuple[Any, Any]] = []

    def _drop_expired(self, now: float) -> None:
        # Recency order is not expiry order: look at every entry, then sort by expiry time.
        # The clock never goes backwards, so whatever expires in a later call expires later
        # than everything already collected.
        gone = [(expires, key) for key, (_, expires) in self._entries.items() if now >= expires]
        gone.sort(key=lambda item: item[0])
        for _, key in gone:
            value, _ = self._entries.pop(key)
            self._expired.append((key, value))

    def _store(self, key: Any, value: Any, now: float) -> None:
        if self._capacity <= 0:
            return
        if key not in self._entries and len(self._entries) >= self._capacity:
            self._entries.popitem(last=False)
        self._entries[key] = (value, now + self._ttl)
        self._entries.move_to_end(key)

    def get(self, key: Any, default: Any = None) -> Any:
        self._drop_expired(self._clock())
        if key not in self._entries:
            return default
        self._entries.move_to_end(key)
        return self._entries[key][0]

    def put(self, key: Any, value: Any) -> None:
        now = self._clock()
        self._drop_expired(now)
        self._store(key, value, now)

    def put_many(self, pairs: list[tuple[Any, Any]]) -> None:
        for key, _ in pairs:
            hash(key)  # an unhashable key raises TypeError here, before anything changes
        now = self._clock()
        self._drop_expired(now)
        for key, value in pairs:
            self._store(key, value, now)

    def pop_expired(self) -> list[tuple[Any, Any]]:
        self._drop_expired(self._clock())
        expired, self._expired = self._expired, []
        return expired

    def __len__(self) -> int:
        self._drop_expired(self._clock())
        return len(self._entries)
EOF
