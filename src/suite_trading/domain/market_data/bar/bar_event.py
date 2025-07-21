from datetime import datetime

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar


class NewBarEvent(Event):
    """Event wrapper carrying bar data with system metadata.

    This event represents the arrival of new bar data in the trading system.
    It contains both the pure bar data and event processing metadata.

    Attributes:
        bar (Bar): The pure bar data object containing OHLC information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
    """

    def __init__(self, bar: Bar, dt_received: datetime):
        """Initialize a new bar event.

        Args:
            bar: The pure bar data object containing OHLC information.
            dt_received: When the event entered our system (timezone-aware UTC).
        """
        self._bar = bar
        self._dt_received = dt_received

    @property
    def bar(self) -> Bar:
        """Get the bar data."""
        return self._bar

    @property
    def dt_received(self) -> datetime:
        """Get the received timestamp."""
        return self._dt_received

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the bar period ended.

        For bar events, this is the end time of the bar period.

        Returns:
            datetime: The bar end timestamp.
        """
        return self.bar.end_dt

    def __str__(self) -> str:
        """Return a string representation of the bar event.

        Returns:
            str: A human-readable string representation.
        """
        return f"{self.__class__.__name__}(bar={self.bar}, dt_received={self.dt_received})"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the bar event.

        Returns:
            str: A detailed string representation.
        """
        return f"{self.__class__.__name__}(bar={self.bar!r}, dt_received={self.dt_received!r})"

    def __eq__(self, other) -> bool:
        """Check equality with another bar event.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if bar events are equal, False otherwise.
        """
        if not isinstance(other, NewBarEvent):
            return False
        return self.bar == other.bar and self.dt_received == other.dt_received
