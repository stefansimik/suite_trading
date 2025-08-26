from decimal import Decimal
from typing import Union


def round_to_increment(price: Union[float, Decimal], increment: Decimal) -> Decimal:
    """
    Round a price to the nearest valid price increment.

    Args:
        price: The price to round
        increment: The price increment to round to

    Returns:
        The price rounded to the nearest increment
    """
    # Convert to Decimal for precise arithmetic
    price_decimal = Decimal(str(price))

    # Calculate how many increments fit into the price
    increments = price_decimal / increment

    # Round to the nearest whole number of increments
    rounded_increments = increments.quantize(Decimal("1"))

    # Convert back to price by multiplying by increment
    return rounded_increments * increment


def ceil_to_multiple(n: int, m: int) -> int:
    """
    Ceil $n to the next multiple of $m. If $n is already a multiple, returns $n.

    Args:
        n: The integer to round up.
        m: The positive multiple base.

    Returns:
        The smallest integer that is a multiple of $m and >= $n.

    Raises:
        ValueError: If $m <= 0.

    Examples:
        >>> ceil_to_multiple(0, 5)
        0
        >>> ceil_to_multiple(1, 5)
        5
        >>> ceil_to_multiple(5, 5)
        5
        >>> ceil_to_multiple(14, 5)
        15
    """
    if m <= 0:
        raise ValueError("m must be a positive integer")
    return ((n + m - 1) // m) * m
