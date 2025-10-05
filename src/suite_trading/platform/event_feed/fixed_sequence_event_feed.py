from collections import deque
from datetime import datetime
from typing import Deque, Iterable, Callable
import logging

from suite_trading.domain.event import Event
from suite_trading.platform.event_feed.event_feed import EventFeed  # noqa: F401 (protocol reference)
from suite_trading.utils.datetime_utils import require_utc


logger = logging.getLogger(__name__)


class FixedSequenceEventFeed:
    """EventFeed that returns a predefined, fixed sequence of events.

    Typical usage:
    - Often used in tests and demos as a simple, in-memory source of events.
    - Also useful whenever you intentionally want to deliver a fixed set of events as-is.

    Behavior:
    - Consumes events in the exact order they are provided (left to right); they may be non-chronological (probably useful for tests).
    - Considered finished when the internal queue of events is empty OR when this EventFeed is closed.
    - Listeners are invoked by TradingEngine after each successful pop().

    Notes:
    - Input can be in any order; this feed intentionally does not reorder or validate events
    - If $events is a deque, it will be consumed in-place by this feed; pass a copy if you need to reuse it elsewhere.

    Example:
        feed = FixedSequenceEventFeed([e1, e2, e3])
        assert feed.peek() is e1
        assert feed.pop() is e1
        feed.remove_events_before(e2.dt_event)
    """

    # region Init

    def __init__(
        self,
        events: Iterable[Event],
    ) -> None:
        """Create a fixed-sequence feed from $events.

        Args:
            events (Iterable[Event]): Events delivered exactly in the provided order.
        """
        # Internal state
        self._closed: bool = False
        self._listeners: dict[str, Callable[[Event], None]] = {}

        # Materialize provided iterable into a deque
        if isinstance(events, deque):
            self._event_deque: Deque[Event] = events
        else:
            self._event_deque = deque(events)

    # endregion

    # region EventFeed protocol

    def peek(self) -> Event | None:
        """Return the next event without consuming it.

        Returns:
            Event | None: The next event, or None if no event is available or the feed is closed.
        """
        if self._closed or not self._event_deque:
            return None
        return self._event_deque[0]

    def pop(self) -> Event | None:
        """Return the next event and advance the feed.

        Returns:
            Event | None: The next event, or None if no event is available or the feed is closed.

        Notes:
            Listeners for this EventFeed are invoked by TradingEngine after a successful pop().
        """
        if self._closed or not self._event_deque:
            return None
        event = self._event_deque.popleft()
        return event

    def is_finished(self) -> bool:
        """Return True when this feed will not produce any more events."""
        return self._closed or not self._event_deque

    def close(self) -> None:
        """Release resources used by this feed.

        Requirements:
        - Idempotent: Safe to call multiple times.
        - Non-blocking: Should not wait for long-running operations.
        """
        if self._closed:
            return
        self._event_deque.clear()
        self._listeners.clear()
        self._closed = True

    def remove_events_before(self, cutoff_time: datetime) -> None:
        """Remove all events with $dt_event < $cutoff_time.

        Args:
            cutoff_time (datetime): Inclusive lower bound (UTC); events older than this are removed.

        Raises:
            ValueError: If $cutoff_time is not timezone-aware UTC.
        """
        # Check: enforce UTC cutoff for consistent comparisons
        require_utc(cutoff_time)
        if self._closed or not self._event_deque:
            return
        # Remove all events with dt_event < cutoff_time anywhere in the queue; preserve order of remaining
        self._event_deque = deque(ev for ev in self._event_deque if ev.dt_event >= cutoff_time)

    def add_listener(self, key: str, listener: Callable[[Event], None]) -> None:
        """Register a listener for events consumed from this feed.

        Notes:
            Listeners are invoked by TradingEngine after each successful pop() from this feed.

        Args:
            key (str): Unique identifier for the listener.
            listener (Callable[[Event], None]): Callback called with the popped Event.

        Raises:
            ValueError: If $key is empty or already registered.
        """
        # Check: ensure $key is non-empty
        if not key:
            raise ValueError("Cannot call `add_listener` because $key is empty")
        # Check: ensure $key is unique among listeners
        if key in self._listeners:
            raise ValueError(f"Cannot call `add_listener` because $key ('{key}') already exists. Use a unique key or call `remove_listener` first.")
        self._listeners[key] = listener

    def remove_listener(self, key: str) -> None:
        """Unregister listener under $key.

        Args:
            key (str): Key of the listener to remove.

        Notes:
            Logs a warning when $key is unknown.
        """
        if key not in self._listeners:
            logger.warning(f"Attempted to remove listener $key ('{key}') from EventFeed (class {self.__class__.__name__}): key not found")
            return
        del self._listeners[key]

    def list_listeners(self) -> list[Callable[[Event], None]]:
        """Return listeners in registration order.

        Returns:
            list[Callable[[Event], None]]: Registered listeners in registration order.
        """
        return list(self._listeners.values())

    # endregion

    # region String representations

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(remaining={len(self._event_deque)}, closed={self._closed})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(remaining={len(self._event_deque)!r}, closed={self._closed!r})"

    # endregion
