from typing import Protocol, Optional, Callable
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

    def peek(self) -> Optional[Event]:
        """Return the next event without consuming it, or None if none is ready."""
        ...

    def pop(self) -> Optional[Event]:
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

        Why this matters:
        Each strategy maintains its own timeline that starts when it processes its first event.
        As events are processed chronologically, the strategy's timeline moves forward.

        When you add a new event feed to an already-running strategy, we must maintain chronological order. The strategy cannot process events that are "in the past" relative to its current timeline position.

        Example scenario:
        - Strategy starts at 9:00 AM, processes events until 9:15 AM
        - At 9:15 AM, we add a new event feed containing older data
        - We must remove all events before 9:15 AM to keep timeline integrity
        - Strategy continues processing only events from 9:15 AM forward
        """
        ...

    def list_listeners(self) -> list[Callable[[Event], None]]:
        """Return all registered listeners for this EventFeed in registration order."""
        ...
