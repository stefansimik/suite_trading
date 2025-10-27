from __future__ import annotations

from typing import Protocol, TYPE_CHECKING
from suite_trading.domain.market_data.order_book import OrderBook

if TYPE_CHECKING:
    from suite_trading.domain.market_data.price_sample import PriceSample


# region Interface


class MarketDepthModel(Protocol):
    """Builds a modeled `OrderBook` from a `PriceSample` for fill simulation.

    Why convert `PriceSample` to `OrderBook`?
    - Customizable simulation surface to encode spread, depth, slippage, liquidity.
    - Separation of concerns: Brokers match against an `OrderBook` without knowing how it
      was modeled.
    - Deterministic matching: Explicit best bid/ask (and levels) for predictable tests.

    Args:
        sample: Latest price sample for an instrument.

    Returns:
        An `OrderBook` snapshot. Brokers typically use best bid/ask; deeper levels may be
        provided for advanced matching.
    """

    def build_simulated_order_book(self, sample: PriceSample) -> OrderBook:  # pragma: no cover
        ...


# endregion
