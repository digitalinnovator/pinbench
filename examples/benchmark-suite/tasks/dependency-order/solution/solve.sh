#!/bin/bash
cat > /app/deps.py <<'PY'
import heapq
from collections import deque

Graph = dict[str, set[str]]


class CycleError(Exception):
    """Raised when the dependencies contain a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        super().__init__("dependency cycle: " + " -> ".join(cycle))
        self.cycle = cycle


def _needs(deps: dict[str, list[str]]) -> Graph:
    """Map every package, listed or only depended on, to the set of its dependencies."""
    needs: Graph = {}
    for package, names in deps.items():
        needs.setdefault(package, set()).update(names)
        for dep in names:
            needs.setdefault(dep, set())
    return needs


def _needed_by(needs: Graph) -> Graph:
    needed_by: Graph = {package: set() for package in needs}
    for package, names in needs.items():
        for dep in names:
            needed_by[dep].add(package)
    return needed_by


def _cycle_through(needs: Graph, start: str) -> list[str] | None:
    """Return the cycle to report if `start` lies on one, else None.

    A breadth-first search reaches the packages nearest first, so the first package found to
    depend on `start` closes a cycle with the fewest packages. Visiting dependencies in sorted
    order keeps each level of the queue in the order of the lists that lead there, so that
    cycle is also the smallest list among the cycles of that size.
    """
    parent: dict[str, str] = {}
    queue = deque([start])
    while queue:
        package = queue.popleft()
        for dep in sorted(needs[package]):
            if dep == start:
                path = [package]
                while path[-1] != start:
                    path.append(parent[path[-1]])
                return path[::-1]
            if dep not in parent:
                parent[dep] = package
                queue.append(dep)
    return None


def _order(needs: Graph, waits_for: Graph, frees: Graph) -> list[str]:
    """Place the smallest ready package each time.

    `waits_for[p]` holds the packages that must be placed before `p`, and `frees[p]` the
    packages that wait for `p`. A cycle is always reported along `needs`, whichever way the
    order runs.
    """
    waiting = {package: len(before) for package, before in waits_for.items()}
    ready = [package for package, count in waiting.items() if count == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        package = heapq.heappop(ready)
        order.append(package)
        for other in frees[package]:
            waiting[other] -= 1
            if waiting[other] == 0:
                heapq.heappush(ready, other)

    if len(order) < len(needs):
        # Every package on a cycle is still unplaced. Trying the unplaced packages smallest
        # first means the first one that lies on a cycle is the smallest package on any cycle.
        for package in sorted(set(needs) - set(order)):
            cycle = _cycle_through(needs, package)
            if cycle is not None:
                raise CycleError(cycle)
    return order


def install_order(deps: dict[str, list[str]]) -> list[str]:
    """Return every package once, in the order in which to install them."""
    needs = _needs(deps)
    return _order(needs, needs, _needed_by(needs))


def remove_order(deps: dict[str, list[str]]) -> list[str]:
    """Return every package once, in the order in which to remove them."""
    needs = _needs(deps)
    return _order(needs, _needed_by(needs), needs)
PY
