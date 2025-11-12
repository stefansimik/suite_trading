from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.market_data.order_book import OrderBook


# region Interface


class MarketDepthModel(Protocol):
    """Protocol for enriching canonical OrderBooks with market microstructure.

    Purpose:
        Take a canonical (thin/zero-spread) OrderBook from the converter and return
        an enriched version with added spread, depth, and liquidity modeling. This
        allows different brokers to test with different market microstructure assumptions.

    Enrichment may include:
        - Adding spread for zero-spread books (realistic bid/ask)
        - Adding depth for thin books (multiple price levels)
        - Modeling slippage and market impact
        - Broker-specific liquidity assumptions

    Notes:
        - Implementations may return the input unchanged (pass-through) or create
          a new OrderBook with added microstructure.
        - The enriched OrderBook is used for order matching by the broker.
    """

    def enrich_order_book(self, canonical_book: OrderBook) -> OrderBook:
        """Enrich canonical OrderBook with market microstructure.

        Takes a canonical (thin/zero-spread) OrderBook and returns an enriched
        version with added spread, depth, and liquidity modeling.

        Args:
            canonical_book: Canonical OrderBook from converter (thin/zero-spread).

        Returns:
            OrderBook: Enriched OrderBook with market microstructure applied.
        """
        ...


# endregion
