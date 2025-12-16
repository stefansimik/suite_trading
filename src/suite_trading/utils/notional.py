from __future__ import annotations

from decimal import Decimal


def compute_notional_value(price: Decimal, quantity: Decimal, contract_size: Decimal) -> Decimal:
    """Compute absolute notional value for $quantity at $price.

    Returns the positive magnitude |$price| * |$quantity| * $contract_size.

    Args:
        price: Trade price; negative values are allowed in some markets.
        quantity: Contract/lot quantity; sign indicates direction but is ignored here.
        contract_size: Contracts-to-notional multiplier (must be positive).

    Returns:
        Absolute notional magnitude as a Decimal.

    Raises:
        ValueError: If $contract_size <= 0.
    """
    # Precondition: contract size must be positive to produce a valid notional scale
    if contract_size <= 0:
        raise ValueError(f"Cannot call `compute_notional_value` because $contract_size ({contract_size}) is not positive")

    # Use absolute values to support negative prices and short exposure (Guideline 7.1)
    return abs(price) * abs(quantity) * contract_size
