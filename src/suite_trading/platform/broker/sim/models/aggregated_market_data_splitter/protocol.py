from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.price_sample import PriceSample


class AggregatedMarketDataSplitter(Protocol):
    """Convert aggregated market‑data events into `PriceSample` items.

    Purpose:
        Provide a minimal, pluggable interface the engine uses to turn aggregated
        market‑data events (e.g., `BarEvent`, `QuoteTickEvent`, `TradeTickEvent`)
        into a sequence of `PriceSample` items that brokers can consume.

    Notes:
        - Implementations typically dispatch by concrete $event type and should
          yield samples in the exact order they ought to be processed by the
          simulation.
        - Prices may be negative when the market supports them; do not filter or
          reject negative values.
        - Use `PriceType` values (BID, ASK, MID, LAST_TRADE); do not use the term
          "mark price" anywhere.

    Example:
        splitter.can_event_be_splitted(event)
        for sample in splitter.split_event_into_price_samples(event):
            broker.process_price_sample(sample)
    """

    def can_event_be_splitted(self, event: Event) -> bool:
        """Return whether this splitter supports the given $event instance.

        Args:
            event: The aggregated market‑data $event to check.

        Returns:
            bool: True if this splitter knows how to split the given $event
            into `PriceSample` items; False otherwise.
        """
        ...

    def split_event_into_price_samples(self, event: Event) -> Iterator[PriceSample]:
        """Yield `PriceSample` items for the given aggregated $event.

        Args:
            event: A supported aggregated market‑data $event to split.

        Returns:
            Iterator[PriceSample]: Lazy iterator producing `PriceSample` items in
            the order they should be processed by the simulation.

        Raises:
            ValueError: Implementations may raise if the $event type is not
            supported. The engine usually calls `can_event_be_splitted` first to
            avoid this.
        """
        ...
