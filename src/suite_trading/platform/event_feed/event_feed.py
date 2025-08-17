from typing import Protocol, Optional
from datetime import datetime
from suite_trading.domain.event import Event


class EventFeed(Protocol):
    """A simple, non-blocking stream of events in time order.

    How to use:
    - Call pop() to get the next ready event.
    - Call peek() to see the next event without consuming it.
    - If pop()/peek() returns None and is_finished() is False, try later.
    - If is_finished() is True, the feed has no more events.

    Tip:
    - In tight loops, use `peek() is not None` as the readiness check.
    """

    def peek(self) -> Optional[Event]:
        """Return the next event without consuming it, or None if none is ready."""
        ...

    def pop(self) -> Optional[Event]:
        """Return the next event and advance the feed, or None if none is ready."""
        ...

    def is_finished(self) -> bool:
        """Return True when this feed is at the end and will not produce any more events."""
        ...

    @property
    def metadata(self) -> Optional[dict]:
        """Optional metadata describing this feed.

        - Plain dict with no value type restrictions.
        - Return None or {} when absent.
        - Typical keys may include 'source_event_feed_provider_name'.
        """
        ...

    def close(self) -> None:
        """Release resources used by this feed.

        Requirements:
        - Idempotent: Safe to call multiple times.
        - Non-blocking: Should not wait for long-running operations.
        - Responsibility: Close connections, files, threads, or other external resources.

        Examples:
            # Simple feed - no cleanup needed
            def close(self) -> None:
                pass

            # Database or network feed - real cleanup needed
            def close(self) -> None:
                if self._connection is not None:
                    self._connection.close()
                    self._connection = None

        Raises:
            Exception: Implementations should raise on unexpected cleanup failures.
        """
        ...

    def remove_events_before(self, cutoff_time: datetime) -> None:
        """Remove all events before $cutoff_time from this event feed.

        Why this matters:
        Each strategy maintains its own timeline that starts when it processes its first event.
        As events are processed chronologically, the strategy's timeline moves forward.

        When you add a new event feed to an already-running strategy, we must maintain
        chronological order. The strategy cannot process events that are "in the past"
        relative to its current timeline position.

        Think of it like a movie: if you're watching from minute 30, you can't suddenly
        jump back to minute 10 without breaking the story flow.

        Example scenario:
        - Strategy starts at 9:00 AM, processes events until 9:15 AM
        - At 9:15 AM, we add a new event feed containing data from 8:00 AM onwards
        - We must remove all events before 9:15 AM to keep timeline integrity and continue in chronological order
        - Strategy continues processing only events from 9:15 AM forward

        Args:
            cutoff_time: Events with dt_event before this time will be removed from the feed.
                This is typically the strategy's current timeline position.

        Raises:
            Exception: Implementations should raise on unexpected errors during filtering.
        """
        ...
