"""Sales tax on a single amount."""


def line_tax(amount, rate):
    """Tax due on `amount` at `rate`; `rate` is a fraction such as "0.0825"."""
    return round(float(amount) * float(rate), 2)
