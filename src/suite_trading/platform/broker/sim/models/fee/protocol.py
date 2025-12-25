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
        proposed_fill: ProposedFill,
        order: Order,
        previous_order_fills: Sequence[OrderFill],
    ) -> Money:
        """Computes the commission specifically for the $proposed_fill part of an order.

        The $proposed_fill is the primary subject of the calculation. The $order and
        $previous_order_fills are provided as secondary context if the model needs
        instrument details or account history.

        Args:
            proposed_fill: The specific trade data (price and quantity) for which to
                calculate the commission.
            order: The order that generated this fill. Use this for instrument details
                or to check other trades for the same order.
            previous_order_fills: The account's history of previous trades. Use this
                to calculate volume-based tiered fees.

        Returns:
            The commission amount as Money.
        """
        ...


# endregion
