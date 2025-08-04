from abc import ABC, abstractmethod
from datetime import datetime


class Event(ABC):
    """Abstract base class for all event objects entering the TradingEngine from external sources.

    This class ensures consistent structure for event object handling, sorting, and processing
    across different object types (bars, ticks, quotes, time events, etc.).

    All event objects must be sortable to enable correct chronological processing order.
    """

    def __init__(self, provider_name: str):
        """Initialize event with provider identification.

        Args:
            provider_name: Name of the provider that generated this event.
        """
        self._provider_name = provider_name

    @property
    def provider_name(self) -> str:
        """Get the name of the provider that generated this event.

        Returns:
            str: Name of the source provider.
        """
        return self._provider_name

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
