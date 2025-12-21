from __future__ import annotations

from typing import Protocol

from suite_trading.domain.market_data.order_book.order_book import OrderBook


# region Interface


class MarketDepthModel(Protocol):
    """Protocol for customizing the liquidity available for matching our orders.

    This model allows you to tailor the OrderBook to meet specific simulation
    requirements. It defines exactly what liquidity—the volume available at
    various price levels—is provided specifically for fulfilling 'our' orders
    within the simulated environment.

    By customizing the matching liquidity, you can:
    - **Simulate thin markets**: Lower the available volume to test how larger
      orders are filled or to simulate increased slippage.
    - **Model deep markets**: Increase liquidity to test strategy capacity
      without realistic market impact.
    - **Tailor spreads**: Adjust the gap between bid and ask to reflect
      broker-specific execution environments or wider market conditions.

    The resulting OrderBook is used by the broker as the single source of truth
    for order matching, margin calculations, and reporting.
    """

    def customize_matching_liquidity(self, order_book: OrderBook) -> OrderBook:
        """Customize the OrderBook liquidity to represent what is available for matching.

        Args:
            order_book: The raw OrderBook snapshot from the market data feed.

        Returns:
            A customized OrderBook representing the specific liquidity available
            for fulfilling our orders at this timestamp.
        """
        ...


# endregion
