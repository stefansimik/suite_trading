from dataclasses import dataclass
from datetime import datetime

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick


@dataclass(frozen=True)
class NewQuoteTickEvent(Event):
    """Event wrapper carrying quote tick data with system metadata.

    This event represents the arrival of new quote tick data in the trading system.
    It contains both the pure quote tick data and event processing metadata.

    Attributes:
        quote_tick (QuoteTick): The pure quote tick data object containing bid/ask information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
    """

    quote_tick: QuoteTick
    dt_received: datetime

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the quote was recorded.

        For quote tick events, this is the timestamp when the quote was captured.

        Returns:
            datetime: The quote timestamp.
        """
        return self.quote_tick.timestamp
