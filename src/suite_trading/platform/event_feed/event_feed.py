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
        """Return True when this feed will not produce any more events."""
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

        Returns:
            None

        Raises:
            Exception: Implementations should raise on unexpected cleanup failures.
        """
        ...

    def remove_events_before(self, cutoff_time: datetime) -> int:
        """Remove all events with dt_event < cutoff_time.

        This method is used to maintain timeline consistency when strategies request new event
        feeds during runtime. If a strategy already has a last_event_time, any events older than
        that time should be filtered out to prevent timeline corruption.

        The method should efficiently remove events that occur before the specified cutoff time
        without affecting the feed's ability to deliver remaining events in chronological order.

        Args:
            cutoff_time: Events with dt_event before this time will be removed from the feed.

        Returns:
            int: Number of events that were removed from the feed.

        Raises:
            Exception: Implementations should raise on unexpected errors during filtering.
        """
        ...
