#!/bin/bash
# Careless solution: one ordering routine that takes "what must come first", called with the
# dependency graph for installing and with the inverted graph for removing. The cycle search is
# a recursive depth-first walk of whichever graph the routine was given. It reports the first
# cycle it finds through the smallest package, which need not be the one with the fewest
# packages; `remove_order` reports a cycle backwards; and a long cycle overflows the stack.
cat > /app/deps.py <<'PY'
import heapq


class CycleError(Exception):
    """Raised when the dependencies contain a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        super().__init__("dependency cycle: " + " -> ".join(cycle))
        self.cycle = cycle


def _graph(deps: dict[str, list[str]]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for package, names in deps.items():
        graph.setdefault(package, set()).update(names)
        for dep in names:
            graph.setdefault(dep, set())
    return graph


def _inverted(graph: dict[str, set[str]]) -> dict[str, set[str]]:
    inverted: dict[str, set[str]] = {package: set() for package in graph}
    for package, names in graph.items():
        for dep in names:
            inverted[dep].add(package)
    return inverted


def _find_cycle(before: dict[str, set[str]], start: str) -> list[str] | None:
    path: list[str] = []
    seen: set[str] = set()

    def visit(package: str) -> bool:
        path.append(package)
        seen.add(package)
        for other in sorted(before[package]):
            if other == start:
                return True
            if other not in seen and visit(other):
                return True
        path.pop()
        return False

    return path if visit(start) else None


def _order(before: dict[str, set[str]]) -> list[str]:
    """Order the packages so that everything in `before[p]` comes ahead of `p`."""
    after = _inverted(before)
    waiting = {package: len(names) for package, names in before.items()}
    ready = [package for package, count in waiting.items() if count == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        package = heapq.heappop(ready)
        order.append(package)
        for other in after[package]:
            waiting[other] -= 1
            if waiting[other] == 0:
                heapq.heappush(ready, other)
    if len(order) < len(before):
        for package in sorted(set(before) - set(order)):
            cycle = _find_cycle(before, package)
            if cycle is not None:
                raise CycleError(cycle)
    return order


def install_order(deps: dict[str, list[str]]) -> list[str]:
    """Return every package once, in the order in which to install them."""
    return _order(_graph(deps))


def remove_order(deps: dict[str, list[str]]) -> list[str]:
    """Return every package once, in the order in which to remove them."""
    return _order(_inverted(_graph(deps)))
PY
