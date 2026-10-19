def make_change(
    amount: int, inventory: dict[int, int], reserve: int = 0
) -> dict[int, int] | None:
    """Pick coins from `inventory` that sum to `amount`; None when that is impossible."""
    raise NotImplementedError


def pay_out(
    amounts: list[int], inventory: dict[int, int], reserve: int = 0
) -> list[dict[int, int]] | None:
    """Pay each amount in turn out of `inventory`; None when one of them cannot be paid."""
    raise NotImplementedError
