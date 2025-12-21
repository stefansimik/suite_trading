from __future__ import annotations

from typing import Protocol

from suite_trading.domain.market_data.order_book.order_book import OrderBook


# region Interface


class MarketDepthModel(Protocol):
    """Protocol for enriching thin OrderBooks with market microstructure.

    Purpose:
        Take a thin or zero-spread OrderBook from the converter and return an
        enriched version with added spread, depth, and liquidity modeling. This
        allows different brokers to test with different market microstructure
        assumptions.

    Enrichment may include:
        - Adding spread for zero-spread books (realistic bid/ask)
        - Adding depth for thin books (multiple price levels)
        - Modeling slippage and market impact
        - Broker-specific liquidity assumptions

    Notes:
        - Implementations may return the input unchanged (pass-through) or create
          a new OrderBook with added microstructure.
        - The enriched OrderBook becomes the broker's current OrderBook used as the
          single source of pricing truth for matching, margin, and logging at that
          timestamp.
    """

    def enrich_order_book(self, order_book: OrderBook) -> OrderBook:
        """Return an enriched OrderBook snapshot for trading, margin, and logging.

        Implementations may adjust spreads, depth, or liquidity based on broker
        assumptions, but must preserve $instrument and $timestamp from the input
        $order_book. The returned OrderBook becomes the single source of truth
        for this timestamp inside simulated brokers.

        Args:
            order_book: Input OrderBook snapshot to enrich.

        Returns:
            OrderBook: Enriched OrderBook snapshot for this timestamp.
        """
        ...


# endregion
