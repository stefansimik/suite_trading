from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick
from suite_trading.utils.datetime_utils import format_dt


class QuoteTickEvent(Event):
    """Event wrapper carrying quote tick data with system metadata.

    This event represents the arrival of new quote tick data in the trading system.
    It contains both the pure quote tick data and event processing metadata.

    Attributes:
        quote_tick (QuoteTick): The pure quote tick data object containing bid/ask information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
    """

    __slots__ = ("_quote_tick",)

    def __init__(self, quote_tick: QuoteTick, dt_received: datetime):
        """Initialize a new quote tick event.

        Args:
            quote_tick: The pure quote tick data object containing bid/ask information.
            dt_received: When the event entered our system (timezone-aware UTC).
        """
        super().__init__(dt_event=quote_tick.timestamp, dt_received=dt_received)
        self._quote_tick = quote_tick

    @property
    def quote_tick(self) -> QuoteTick:
        """Get the quote tick data."""
        return self._quote_tick

    @property
    def dt_received(self) -> datetime:
        """Get the received timestamp."""
        return self._dt_received

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the quote was recorded.

        For quote tick events, this is the timestamp when the quote was captured.

        Returns:
            datetime: The quote timestamp.
        """
        return self.quote_tick.timestamp

    # region PriceSampleSource implementation

    def iter_price_samples(self) -> Iterator[PriceSample]:
        """Yield BID then ASK `PriceSample` from $quote_tick in deterministic order."""
        q = self.quote_tick
        dt = self.dt_event
        inst = q.instrument

        # Emit best bid then best ask using existing Decimal values
        yield PriceSample(inst, dt, PriceType.BID, q.bid_price)
        yield PriceSample(inst, dt, PriceType.ASK, q.ask_price)

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(quote_tick={self.quote_tick}, dt_received={format_dt(self.dt_received)})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(quote_tick={self.quote_tick!r}, dt_received={format_dt(self.dt_received)})"

    def __eq__(self, other) -> bool:
        """Check equality with another quote tick event.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if quote tick events are equal, False otherwise.
        """
        if not isinstance(other, QuoteTickEvent):
            return False
        return self.quote_tick == other.quote_tick and self.dt_received == other.dt_received

    # endregion
