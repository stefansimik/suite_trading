from __future__ import annotations

from typing import Sequence

from suite_trading.domain.monetary.money import Money
from suite_trading.domain.order.orders import Order
from suite_trading.domain.order.order_fill import OrderFill
from suite_trading.domain.market_data.order_book.order_book import ProposedFill

from .protocol import FeeModel


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
        proposed_fill: ProposedFill,
        previous_order_fills: Sequence[OrderFill],
    ) -> Money:
        """Computes the commission for a trade.

        This model multiplies the fixed fee by the absolute number of units filled.

        Args:
            order: The order being filled.
            proposed_fill: The trade price and quantity before fees are added.
            previous_order_fills: The account's previous trades. Not used in this model.

        Returns:
            The commission amount as Money.
        """
        signed_quantity = proposed_fill.signed_quantity

        # Precondition: ensure non-zero $signed_quantity
        if signed_quantity == 0:
            raise ValueError(f"Cannot call `compute_commission` because $signed_quantity ({signed_quantity}) is zero for order $id ('{order.id}')")

        return self._fee_per_unit * abs(signed_quantity)
