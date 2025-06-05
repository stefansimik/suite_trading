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
