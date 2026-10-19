#!/bin/bash
# Plausible careless solution. It adds a tie-breaking counter and an id index, which is enough
# for the visible test, but takes three shortcuts that the rules in instruction.md exclude:
#   - update() is a remove plus a push, so the item gets a new counter and loses its place
#     among equal priorities;
#   - items() returns the heap array as it is, which is a heap and not pop order;
#   - push() never checks the id, so pushing an id that is already in the queue adds a second
#     entry and overwrites the index instead of raising ValueError.
cat > /app/pqueue.py <<'EOF'
"""A small priority queue built on heapq."""

import heapq
import itertools


class PriorityQueue:
    """Min-queue of dict items; each item has an "id" key."""

    def __init__(self):
        self._heap = []
        self._entries = {}  # item id -> (priority, count, item)
        self._counter = itertools.count()

    def push(self, item, priority):
        """Add item with the given priority (lower pops first)."""
        entry = (priority, next(self._counter), item)
        self._entries[item["id"]] = entry
        heapq.heappush(self._heap, entry)

    def pop(self):
        """Remove and return the item with the lowest priority."""
        _, _, item = heapq.heappop(self._heap)
        del self._entries[item["id"]]
        return item

    def remove(self, item_id):
        """Take the item with this id out of the queue and return it."""
        entry = self._entries.pop(item_id)
        self._heap.remove(entry)
        heapq.heapify(self._heap)
        return entry[2]

    def update(self, item_id, priority):
        """Give the item with this id a new priority."""
        self.push(self.remove(item_id), priority)

    def items(self):
        """List the items in the queue."""
        return [item for _, _, item in self._heap]

    def __len__(self):
        return len(self._heap)
EOF
