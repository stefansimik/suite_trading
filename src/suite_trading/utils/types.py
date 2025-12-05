from __future__ import annotations

from decimal import Decimal


def as_decimal(value: Decimal | str | int | float) -> Decimal:
    """Convert supported scalar types into Decimal.

    This helper centralizes Decimal conversion so that tests and utilities
    do not re-implement the same logic.

    Args:
        value: Input value as Decimal, string, int or float.

    Returns:
        Value converted to Decimal.
    """

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))
