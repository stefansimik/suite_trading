from __future__ import annotations
from collections.abc import Iterator
from typing import Protocol, runtime_checkable
from suite_trading.domain.market_data.price_sample import PriceSample


@runtime_checkable
class PriceSampleIterable(Protocol):
    """Marker Protocol for events that carry price information.

    Public API used by broker/matching engine and any consumer that needs to extract
    price observations from heterogeneous event types (bars, trade ticks, quote ticks).

    Implementations must yield deterministic sequences of `PriceSample` items.

    Notes:
    - No additional getters are required; each `PriceSample` includes instrument and time.
    - Bars should not expose OHLC semantics here; use `PriceSample.price_type` instead.
    """

    def iter_price_samples(self) -> Iterator[PriceSample]:
        """Yield `PriceSample` items in deterministic order."""
        ...
