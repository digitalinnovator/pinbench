class CycleError(Exception):
    """Raised when the dependencies contain a cycle."""

    def __init__(self, cycle: list[str]) -> None:
        super().__init__("dependency cycle: " + " -> ".join(cycle))
        self.cycle = cycle


def install_order(deps: dict[str, list[str]]) -> list[str]:
    """Return every package once, in the order in which to install them."""
    raise NotImplementedError


def remove_order(deps: dict[str, list[str]]) -> list[str]:
    """Return every package once, in the order in which to remove them."""
    raise NotImplementedError
