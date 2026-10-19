#!/bin/bash
cat > /app/pqueue.py <<'EOF'
"""A small priority queue built on heapq."""

import heapq
import itertools


class PriorityQueue:
    """Min-queue of dict items; each item has an "id" key.

    The heap holds (priority, order, serial, item) entries. `order` is the item's place in push
    order and breaks ties between equal priorities. `serial` is unique per heap entry, so two
    entries never fall through to comparing their dicts.

    remove() and update() leave the old entry in the heap. An entry is live only while `_live`
    maps its item's id to that very entry; pop() discards the others and items() never sees
    them, because it reads `_live` rather than the heap.
    """

    def __init__(self):
        self._heap = []
        self._live = {}  # item id -> its live (priority, order, serial, item) entry
        self._orders = itertools.count()
        self._serials = itertools.count()

    def _add(self, item, priority, order):
        entry = (priority, order, next(self._serials), item)
        self._live[item["id"]] = entry
        heapq.heappush(self._heap, entry)

    def push(self, item, priority):
        """Add item with the given priority (lower pops first)."""
        if item["id"] in self._live:
            raise ValueError(f"id already in the queue: {item['id']!r}")
        self._add(item, priority, next(self._orders))

    def pop(self):
        """Remove and return the item with the lowest priority."""
        while self._heap:
            entry = heapq.heappop(self._heap)
            item = entry[3]
            live = self._live.get(item["id"])
            if live is not None and live[2] == entry[2]:
                del self._live[item["id"]]
                return item
        raise IndexError("pop from an empty priority queue")

    def remove(self, item_id):
        """Take the item with this id out of the queue and return it."""
        return self._live.pop(item_id)[3]

    def update(self, item_id, priority):
        """Give the item a new priority; it keeps its place in push order."""
        _, order, _, item = self._live[item_id]
        self._add(item, priority, order)

    def items(self):
        """List the items in the order pop() would return them; the queue is not changed."""
        return [entry[3] for entry in sorted(self._live.values(), key=lambda e: e[:3])]

    def __len__(self):
        return len(self._live)
EOF
