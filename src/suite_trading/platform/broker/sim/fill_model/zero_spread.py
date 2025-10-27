from __future__ import annotations

from suite_trading.domain.market_data.order_book import OrderBook, BookLevel
from suite_trading.domain.market_data.price_sample import PriceSample


# region Zero-spread implementation


class ZeroSpreadFillModel:
    """Zero-spread OrderFillModel that builds an `OrderBook` at the sample price.

    - BUY fills at best ask, SELL at best bid (both equal to `$sample.price`).
    - Negative prices are allowed and passed through (Guideline 7.1).
    - Stateless and deterministic; no side effects.
    """

    __slots__ = ()

    def build_simulated_order_book(self, sample: PriceSample) -> OrderBook:
        """Build a zero-spread `OrderBook` from $sample.

        Returns:
            `OrderBook` with identical best bid/ask at `$sample.price` and large depth.
        """
        instrument = sample.instrument
        single_level = BookLevel(
            price=sample.price,
            volume=instrument.quantity_from_lots(100_000_000),
        )
        return OrderBook(instrument=instrument, bids=[single_level], asks=[single_level])

    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"


# endregion
