from __future__ import annotations

from suite_trading.domain.market_data.order_book import OrderBook


# region Zero-spread implementation


class ZeroSpreadMarketDepthModel:
    """Pass-through depth model - uses canonical OrderBook as-is.

    This model performs no enrichment, returning the canonical OrderBook
    unchanged. Suitable for backtesting with zero-spread assumptions or
    when canonical OrderBooks already contain desired liquidity.

    Notes:
        - Stateless and deterministic; no side effects.
        - Negative prices are allowed and passed through.
    """

    __slots__ = ()

    def enrich_order_book(self, canonical_book: OrderBook) -> OrderBook:
        """Return canonical OrderBook unchanged (pass-through).

        Args:
            canonical_book: Canonical OrderBook from converter.

        Returns:
            OrderBook: Same OrderBook instance, no enrichment applied.
        """
        return canonical_book

    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"


# endregion
