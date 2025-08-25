from datetime import datetime

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick


class NewQuoteTickEvent(Event):
    """Event wrapper carrying quote tick data with system metadata.

    This event represents the arrival of new quote tick data in the trading system.
    It contains both the pure quote tick data and event processing metadata.

    Attributes:
        quote_tick (QuoteTick): The pure quote tick data object containing bid/ask information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
    """

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

    def __str__(self) -> str:
        """Return a string representation of the quote tick event.

        Returns:
            str: A human-readable string representation.
        """
        return f"{self.__class__.__name__}(quote_tick={self.quote_tick}, dt_received={self.dt_received})"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the quote tick event.

        Returns:
            str: A detailed string representation.
        """
        return f"{self.__class__.__name__}(quote_tick={self.quote_tick!r}, dt_received={self.dt_received!r})"

    def __eq__(self, other) -> bool:
        """Check equality with another quote tick event.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if quote tick events are equal, False otherwise.
        """
        if not isinstance(other, NewQuoteTickEvent):
            return False
        return self.quote_tick == other.quote_tick and self.dt_received == other.dt_received
