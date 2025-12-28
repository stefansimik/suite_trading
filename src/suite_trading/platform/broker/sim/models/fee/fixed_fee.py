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
        proposed_fill: ProposedFill,
        order: Order,
        previous_order_fills: Sequence[OrderFill],
    ) -> Money:
        """Implements: FeeModel.compute_commission

        Compute the commission for the $proposed_fill.

        This model multiplies the fixed fee by the absolute quantity of the $proposed_fill.

        Args:
            proposed_fill: The trade data for which the commission is calculated.
            order: The order being filled. Not used in this model.
            previous_order_fills: The account's previous trades. Not used in this model.

        Returns:
            The commission amount as Money.
        """
        signed_qty = proposed_fill.signed_qty

        # Raise: ensure signed quantity is non-zero
        if signed_qty == 0:
            raise ValueError(f"Cannot call `compute_commission` because $signed_quantity ({signed_qty}) is zero for order $id ('{order.id}')")

        return self._fee_per_unit * abs(signed_qty)
