from __future__ import annotations

from typing import Iterable, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal

from .protocol import FeeModel

if TYPE_CHECKING:
    from suite_trading.domain.monetary.money import Money
    from suite_trading.domain.order.orders import Order
    from suite_trading.domain.order.order_fill import OrderFill


class FixedFeeModel(FeeModel):
    """Fixed per-unit commission model.

    Args:
        fee_per_unit: Commission $fee_per_unit charged for each 1 unit filled.
            Example: 0.005 USD per share → Money(Decimal("0.005"), USD)
    """

    __slots__ = ("_fee_per_unit",)

    def __init__(self, fee_per_unit: Money) -> None:
        self._fee_per_unit = fee_per_unit

    def compute_commission(
        self,
        order: Order,
        price: Decimal,
        quantity: Decimal,
        timestamp: datetime,
        previous_order_fills: Iterable[OrderFill],
    ) -> Money:
        # Precondition: ensure positive $quantity
        if quantity <= 0:
            raise ValueError(f"Cannot call `compute_commission` because $quantity ({quantity}) <= 0 for order $id ('{order.id}')")

        return self._fee_per_unit * quantity
