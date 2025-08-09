from datetime import datetime
from typing import Optional

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar


class NewBarEvent(Event):
    """Event wrapper carrying bar data with system metadata.

    This event represents the arrival of new bar data in the trading system.
    It contains both the pure bar data and event processing metadata.

    Attributes:
        bar (Bar): The pure bar data object containing OHLC information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
        is_historical (bool): Whether this bar data is historical or live.
    """

    def __init__(
        self,
        bar: Bar,
        dt_received: datetime,
        is_historical: bool,
        metadata: Optional[dict] = None,
    ) -> None:
        """Initialize a new bar event.

        Args:
            bar: The pure bar data object containing OHLC information.
            dt_received: When the event entered our system (timezone-aware UTC).
            is_historical: Whether this bar data is historical or live.
            metadata: Optional metadata (e.g., {'source_event_feed_name': 'feed-A'}). Use None or
                empty dict when absent.
        """
        super().__init__(metadata)
        self._bar = bar
        self._dt_received = dt_received
        self._is_historical = is_historical

    @property
    def bar(self) -> Bar:
        """Get the bar data."""
        return self._bar

    @property
    def dt_received(self) -> datetime:
        """Get the received timestamp."""
        return self._dt_received

    @property
    def is_historical(self) -> bool:
        """Get whether this bar data is historical or live."""
        return self._is_historical

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
        return f"{self.__class__.__name__}(bar={self.bar}, dt_received={self.dt_received}, is_historical={self.is_historical})"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the bar event.

        Returns:
            str: A detailed string representation.
        """
        return f"{self.__class__.__name__}(bar={self.bar!r}, dt_received={self.dt_received!r}, is_historical={self.is_historical!r})"

    def __eq__(self, other) -> bool:
        """Check equality with another bar event.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if bar events are equal, False otherwise.
        """
        if not isinstance(other, NewBarEvent):
            return False
        return self.bar == other.bar and self.dt_received == other.dt_received and self.is_historical == other.is_historical
