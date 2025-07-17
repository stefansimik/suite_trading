from abc import ABC, abstractmethod
from datetime import datetime


class Event(ABC):
    """Abstract base class for all event objects entering the TradingEngine from external sources.

    This class ensures consistent structure for event object handling, sorting, and processing
    across different object types (bars, ticks, quotes, time events, etc.).

    All event objects must be sortable to enable correct chronological processing order.
    """

    @property
    @abstractmethod
    def dt_received(self) -> datetime:
        """Datetime when the event object entered our system.

        This includes network latency and represents when the event was actually
        received by our trading system, not when it was originally created.
        Must be timezone-aware (UTC required).

        Returns:
            datetime: The timestamp when event was received by our system.
        """
        ...

    @property
    @abstractmethod
    def dt_event(self) -> datetime:
        """Event datetime when the event occurred, independent from arrival time.

        This represents the official time for the event (e.g., bar end-time,
        tick timestamp, quote timestamp) and is independent of network delays
        or when the event arrived in our system.
        Must be timezone-aware (UTC required).

        Returns:
            datetime: The event timestamp.
        """
        ...

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Type identifier for the event object.

        Used for easy type distinction and routing to appropriate handlers.
        Should be a simple string identifier like "bar", "trade_tick",
        "quote_tick", "time_event", etc.

        Returns:
            str: The type identifier for this event object.
        """
        ...

    def __lt__(self, other: "Event") -> bool:
        """Enable sorting by event datetime for chronological processing.

        Event objects are sorted primarily by dt_event to ensure correct
        chronological processing order. If dt_event is equal, sort by
        dt_received as secondary criterion.

        Args:
            other (Event): Another event object to compare with.

        Returns:
            bool: True if this event object should be processed before other.
        """
        if self.dt_event != other.dt_event:
            return self.dt_event < other.dt_event
        return self.dt_received < other.dt_received
