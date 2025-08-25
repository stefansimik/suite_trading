from datetime import datetime

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.tick.trade_tick import TradeTick


class NewTradeTickEvent(Event):
    """Event wrapper carrying trade tick data with system metadata.

    This event represents the arrival of new trade tick data in the trading system.
    It contains both the pure trade tick data and event processing metadata.

    Attributes:
        trade_tick (TradeTick): The pure trade tick data object containing trade information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
    """

    def __init__(self, trade_tick: TradeTick, dt_received: datetime):
        """Initialize a new trade tick event.

        Args:
            trade_tick: The pure trade tick data object containing trade information.
            dt_received: When the event entered our system (timezone-aware UTC).
        """
        super().__init__(dt_event=trade_tick.timestamp, dt_received=dt_received, metadata=None)
        self._trade_tick = trade_tick

    @property
    def trade_tick(self) -> TradeTick:
        """Get the trade tick data."""
        return self._trade_tick

    @property
    def dt_received(self) -> datetime:
        """Get the received timestamp."""
        return self._dt_received

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the trade occurred.

        For trade tick events, this is the timestamp when the trade was executed.

        Returns:
            datetime: The trade timestamp.
        """
        return self.trade_tick.timestamp

    def __str__(self) -> str:
        """Return a string representation of the trade tick event.

        Returns:
            str: A human-readable string representation.
        """
        return f"{self.__class__.__name__}(trade_tick={self.trade_tick}, dt_received={self.dt_received})"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the trade tick event.

        Returns:
            str: A detailed string representation.
        """
        return f"{self.__class__.__name__}(trade_tick={self.trade_tick!r}, dt_received={self.dt_received!r})"

    def __eq__(self, other) -> bool:
        """Check equality with another trade tick event.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if trade tick events are equal, False otherwise.
        """
        if not isinstance(other, NewTradeTickEvent):
            return False
        return self.trade_tick == other.trade_tick and self.dt_received == other.dt_received
