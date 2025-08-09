from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class Event(ABC):
    """Abstract base class for all event objects entering the TradingEngine from external sources.

    This class ensures consistent structure for event object handling, sorting, and processing
    across different object types (bars, ticks, quotes, time events, etc.).

    All event objects must be sortable to enable correct chronological processing order.

    Metadata contract:
    - Implementations may attach optional metadata as a dict with no value type restrictions.
    - If no metadata is available, return None or an empty dict.
    - Typical keys may include 'source_event_feed_name'.
    """

    def __init__(self, metadata: Optional[dict] = None) -> None:
        """Initialize event with optional metadata.

        Args:
            metadata: Optional dictionary with event metadata. Use None or {} when absent.
        """
        self._metadata: Optional[dict] = dict(metadata) if metadata is not None else None

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
    def metadata(self) -> Optional[dict]:
        """Optional metadata attached to the event.

        Returns:
            Optional[dict]: A dictionary of metadata or None when absent.
        """
        return self._metadata

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
