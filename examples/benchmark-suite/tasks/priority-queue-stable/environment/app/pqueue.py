"""A small priority queue built on heapq."""

import heapq


class PriorityQueue:
    """Min-queue of dict items; each item has an "id" key."""

    def __init__(self):
        self._heap = []

    def push(self, item, priority):
        """Add item with the given priority (lower pops first)."""
        heapq.heappush(self._heap, (priority, item))

    def pop(self):
        """Remove and return the item with the lowest priority."""
        _, item = heapq.heappop(self._heap)
        return item

    def __len__(self):
        return len(self._heap)
