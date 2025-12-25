from __future__ import annotations

from typing import Protocol, Sequence

from suite_trading.domain.order.orders import Order
from suite_trading.domain.order.order_fill import OrderFill
from suite_trading.domain.monetary.money import Money
from suite_trading.domain.market_data.order_book.order_book import ProposedFill


# region Interface


class FeeModel(Protocol):
    """Domain interface for fee modeling used by the simulated broker.

    The fee is computed from primitive inputs so that `OrderFill` can be constructed with an
    already-known $commission.
    """

    def compute_commission(
        self,
        order: Order,
        proposed_fill: ProposedFill,
        previous_order_fills: Sequence[OrderFill],
    ) -> Money:
        """Computes the commission for a single trade.

        Args:
            order: The order being filled. Use this to access instrument details or
                other fills for this order.
            proposed_fill: The trade price and quantity before fees are added.
            previous_order_fills: The account's previous trades. Use this to handle
                volume-based discounts.

        Returns:
            The commission amount as Money.
        """
        ...


# endregion
