from __future__ import annotations

from suite_trading.domain.market_data.order_book import OrderBook


# region Zero-spread implementation


class ZeroSpreadMarketDepthModel:
    """Pass-through depth model – returns the incoming OrderBook as-is.

    This model performs no enrichment, returning the provided OrderBook
    unchanged. Suitable for backtesting with zero-spread assumptions or
    when upstream OrderBooks already contain the desired liquidity.

    Notes:
        - Stateless and deterministic; no side effects.
        - Negative prices are allowed and passed through.
    """

    __slots__ = ()

    def enrich_order_book(self, order_book: OrderBook) -> OrderBook:
        """Return the provided OrderBook unchanged (pass-through).

        Args:
            order_book: OrderBook snapshot from the converter.

        Returns:
            OrderBook: Same OrderBook instance, no enrichment applied.
        """
        return order_book

    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"


# endregion
