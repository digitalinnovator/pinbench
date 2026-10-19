Implement `install_order(deps)` and `remove_order(deps)` in `/app/deps.py`. `deps` is a dict that
maps each package name (a `str`) to the list of package names it depends on. Each function
returns a list that holds every package exactly once: `install_order` in an order in which the
packages can be installed, `remove_order` in an order in which they can be removed.

Rules:

- A name that appears only inside a dependency list is also a package; it has no dependencies.
- Naming the same dependency several times in one list has the same effect as naming it once.
- A package can be installed once all of its dependencies have been installed. It can be removed
  once every package that depends on it has been removed.
- "Smallest" below always means smallest by plain `str` comparison (what `min()` returns).
- Build each order one package at a time: the next package is always the smallest of the
  packages not yet placed that can be installed (in `install_order`) or removed (in
  `remove_order`) at that point.
- If the dependencies contain a cycle, both functions raise `CycleError(cycle)` instead.
  `CycleError` is already defined in `/app/deps.py` and keeps the list in its `cycle` attribute.
- `cycle` holds each package of one cycle exactly once, arranged so that every package depends
  on the one after it and the last depends on the first.
- A package that depends on itself forms a cycle of one package.
- The reported cycle must contain the smallest of all the packages that lie on some cycle, and
  the list starts with that package. If several cycles qualify, report the one with the fewest
  packages; if several still qualify, report the one whose list is the smallest (lists compared
  with `<`).
- Both functions must work for any `deps` that holds up to 2,000 packages.
- Do not modify `deps` or the lists inside it.

`/app/test_deps.py` holds a starter test. Run it with `python -m pytest -q`.
