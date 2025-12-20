from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.order.orders import Order
    from suite_trading.domain.market_data.order_book.order_book import OrderBook, ProposedFill


# region Interface


class FillModel(Protocol):
    """Protocol for modeling realistic fill behavior in simulation.

    After order matching determines potential fills, FillModel decides which
    fills actually execute and at what prices. This enables modeling:
    - Probabilistic fills (order may not fill even when price touches)
    - Slippage (fill prices differ from OrderBook prices)
    - Partial fills (only portion of available liquidity fills)
    - Queue position (limit order priority in the book)

    FillModel is called after OrderBook.simulate_fills() but before executions
    are recorded, allowing it to filter, modify, or reject proposed fills.
    """

    def apply_fill_policy(
        self,
        order: Order,
        order_book: OrderBook,
        proposed_fills: list[ProposedFill],
    ) -> list[ProposedFill]:
        """Apply fill policy to proposed fills, returning actual fills to execute.

        Args:
            order: Order being filled.
            order_book: Current OrderBook snapshot used for matching.
            proposed_fills: Proposed fills from OrderBook.simulate_fills().

        Returns:
            Filtered/modified list of ProposedFill to actually execute.
        """
        ...


# endregion
