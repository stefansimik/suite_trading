from __future__ import annotations

from decimal import Decimal


def compute_notional_value(price: Decimal, signed_quantity: Decimal, contract_size: Decimal) -> Decimal:
    """Compute abs notional value for $signed_qty at $price.

    Returns the positive magnitude |$price| * |$signed_qty| * $contract_size.

    Args:
        price: Trade price; negative values are allowed in some markets.
        quantity: Contract/lot abs_qty; sign indicates direction but is ignored here.
        contract_size: Contracts-to-notional multiplier (must be positive).

    Returns:
        Abs notional magnitude as a Decimal.

    Raises:
        ValueError: If $contract_size <= 0.
    """
    # Raise: contract size must be positive to produce a valid notional scale
    if contract_size <= 0:
        raise ValueError(f"Cannot call `compute_notional_value` because $contract_size ({contract_size}) is not positive")

    # Use absolute values to support negative prices and short exposure (Guideline 7.1)
    return abs(price) * abs(signed_quantity) * contract_size
