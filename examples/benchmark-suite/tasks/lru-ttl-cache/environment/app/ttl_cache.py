from typing import Any, Callable


class Cache:
    """Least-recently-used cache whose entries also expire."""

    def __init__(self, capacity: int, ttl: float, clock: Callable[[], float]) -> None:
        raise NotImplementedError

    def get(self, key: Any, default: Any = None) -> Any:
        raise NotImplementedError

    def put(self, key: Any, value: Any) -> None:
        raise NotImplementedError

    def put_many(self, pairs: list[tuple[Any, Any]]) -> None:
        raise NotImplementedError

    def pop_expired(self) -> list[tuple[Any, Any]]:
        raise NotImplementedError

    def __len__(self) -> int:
        raise NotImplementedError
