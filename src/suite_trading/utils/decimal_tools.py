from __future__ import annotations

from decimal import Decimal
from typing import TypeAlias


DecimalLike: TypeAlias = Decimal | str | int | float


def as_decimal(value: DecimalLike) -> Decimal:
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
