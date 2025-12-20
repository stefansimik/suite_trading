from __future__ import annotations

from typing import Protocol, Callable
from datetime import datetime
from suite_trading.domain.event import Event


class EventFeed(Protocol):
    """A simple, non-blocking stream of events in time order.

    How to use:
    - Call peek() to see the next event without consuming it.
    - Call pop() to get the next ready event.
    - If pop()/peek() returns None and is_finished() is False, try later.
    - If is_finished() is True, the feed has no more events.

    Listeners:
    - TradingEngine invokes listeners after it pops an event  from EventFeed and processes the callback. That means, EventFeed implementations must not notify listeners themselves (it is done in TradingEngine automatically)
    """

    def peek(self) -> Event | None:
        """Return the next event without consuming it, or None if none is ready."""
        ...

    def pop(self) -> Event | None:
        """Return the next event and advance the feed, or None if none is ready."""
        ...

    def is_finished(self) -> bool:
        """Return True when this feed is at the end and will not produce any more events.
        If event-feed is closed, it is considered also finished."""
        ...

    def close(self) -> None:
        """Release resources used by this feed.

        Requirements:
        - Idempotent: Safe to call multiple times.
        - Non-blocking: Should not wait for long-running operations.
        - Responsibility: Close connections, files, threads, or other external resources.

        Raises:
        - Exception: Implementations should raise on unexpected cleanup failures.
        """
        ...

    def remove_events_before(self, cutoff_time: datetime) -> None:
        """Remove all events before $cutoff_time from this event feed.

        This method is used by `TradingEngine` when attaching an EventFeed to a Strategy
        while the engine is already RUNNING. All strategies in one engine share a single
        simulated timeline, so a newly attached feed must not emit events that are "in
        the past" relative to the engine's current global time.

        Semantics:

        - $cutoff_time is the engine's current global `Event.dt_event` when the feed is
          attached (UTC, timezone-aware).
        - Implementations should drop or skip all events whose effective event time is
          strictly less than $cutoff_time (for example, BarEvent $end_dt or Event.dt_event).
        - Events at or after $cutoff_time remain available and will be delivered in
          global chronological order together with events from other feeds.

        Example scenario (shared timeline):

        - Engine has already processed events up to 9:15 AM.
        - At 9:15 AM, you add a new EventFeed containing older data starting at 9:00 AM.
        - `TradingEngine` calls `remove_events_before(cutoff_time=9:15)` on the new feed.
        - The feed discards all events before 9:15 AM and continues from 9:15 AM forward,
          keeping the global event stream strictly non-decreasing in time.
        """
        ...

    def add_listener(self, key: str, listener: Callable[[Event], None]) -> None:
        """Register a listener for events consumed from this feed.

        Notes:
            Listeners are invoked by TradingEngine after each successful pop() from this feed.

        Args:
            key (str): Unique identifier for the listener.
            listener (Callable[[Event], None]): Callback called with the popped Event.
        """
        ...

    def remove_listener(self, key: str) -> None:
        """Unregister listener under $key.

        Args:
            key (str): Key of the listener to remove.
        """
        ...

    def list_listeners(self) -> list[Callable[[Event], None]]:
        """Return all registered listeners for this EventFeed in registration order."""
        ...
