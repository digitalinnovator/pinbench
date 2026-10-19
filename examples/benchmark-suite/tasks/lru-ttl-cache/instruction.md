Implement the class `Cache` in `/app/ttl_cache.py`: a least-recently-used cache whose entries
also expire. `/app/test_ttl_cache.py` holds one example test. Use only the standard library.

Rules:

- `Cache(capacity, ttl, clock)`: `capacity` is an int >= 0, `ttl` is a positive number and
  `clock` is a zero-argument function that returns the current time, a number that never
  decreases. Read the time only by calling `clock`.
- An entry lives for `ttl` time units after the clock time at which it was stored; once `ttl`
  has fully elapsed it is expired. To `get`, `put`, `put_many` and `len` an expired entry
  behaves in every respect as if it had never been stored.
- `get(key, default=None)` returns the value of a live entry, otherwise `default`. A `get` that
  finds a live entry makes it the most recently used; it does not change when the entry expires.
- `put(key, value)` on a live key replaces its value, restarts its `ttl` from the current clock
  time and makes it the most recently used. Nothing is evicted.
- `put(key, value)` on any other key adds a new entry as the most recently used. If the cache
  already holds `capacity` live entries, the least recently used live entry is evicted first.
  Expired entries never count towards `capacity`.
- `put_many(pairs)` takes a list of `(key, value)` tuples and stores them one after another, in
  list order, exactly as `put` would, all at one reading of the clock. If any key in the list
  is unhashable it raises `TypeError` and leaves the cache exactly as it was.
- `pop_expired()` returns a list of `(key, value)` tuples: one for each entry that has expired
  and was not returned by an earlier `pop_expired()`, ordered by expiry time, earliest first.
  Evicted entries and values replaced by a `put` on a live key are never in it.
- `put` and `put_many` return `None`. A value can be any object, including `None`.
- `len(cache)` is the number of live entries.
- Each call of `get`, `put`, `put_many`, `pop_expired` or `len(cache)` calls `clock` at most
  once.
- With `capacity` 0 nothing is ever stored: `put` has no effect and `put_many` stores nothing.
