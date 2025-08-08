from typing import Protocol, Optional
from datetime import datetime
from suite_trading.domain.event import Event


class EventFeed(Protocol):
    """Simple streaming interface that delivers events in chronological order to strategies.

    This protocol is intentionally minimal and non-blocking. It supports three observable runtime
    scenarios based on data availability.

    Scenarios:
    - NEXT_EVENT_READY: An event is immediately available -> next() returns an Event, peek() returns same Event
    - WAITING_FOR_FUTURE_EVENTS: No event is ready now, but the feed may produce more later -> both return None while
      is_finished() is False
    - FINISHED: The feed will never produce more events -> both return None, is_finished() is True

    | Scenario | peek() | next() | is_finished() |
    |----------|--------|--------|---------------|
    | NEXT_EVENT_READY | Event | Event | False |
    | WAITING_FOR_FUTURE_EVENTS | None | None | False |
    | FINISHED | None | None | True |

    How to use:
    - Call next() repeatedly to pull available events
    - Call peek() to inspect the next event without consuming it
    - If next() or peek() returns None, check is_finished():
      - False => the feed is WAITING_FOR_FUTURE_EVENTS; keep polling later
      - True  => the feed is FINISHED; stop polling
    - Always call close() once you are done to release resources

    Examples:
        # Standard consumption loop
        while not feed.is_finished():
            event = feed.next()
            if event is not None:
                process_event(event)
        feed.close()

        # Conditional lookahead
        preview = feed.peek()
        if preview is not None and should_defer(preview):
            # Decide based on next event without consuming it
            pass

        event = feed.next()
        if event is not None:
            handle(event)

    Notes:
    - Implementations must be non-blocking in both next() and peek()
    - Should fail fast on unexpected errors (raise exceptions rather than silently ignoring problems)
    - Single-consumer expectation; document if implementation supports concurrency
    - This contract intentionally omits advanced controls such as request_stop() or
      finished_reason(). Add such capabilities only when you truly need them, keeping the core API
      simple.
    """

    def peek(self) -> Optional[Event]:
        """Return the next event without consuming it.

        Non-blocking lookahead that returns the same event that next() would return, without
        advancing the feed position. Multiple peek() calls return the same event until next()
        consumes it.

        Scenario mapping:
        - NEXT_EVENT_READY: Returns the head event without consuming it
        - WAITING_FOR_FUTURE_EVENTS: Returns None; is_finished() is False
        - FINISHED: Returns None; is_finished() is True

        Guarantees:
        - If peek() returns event E, the very next next() call must return the same E (object identity)
        - Multiple peek() calls return the same event until consumed by next()
        - Events arriving after peek() but before next() do not change what next() returns

        Returns:
            Optional[Event]: The next event if available, otherwise None.

        Raises:
            Exception: Implementations should raise on unexpected errors instead of hiding them.
        """
        ...

    def next(self) -> Optional[Event]:
        """Return the next event if one is ready.

        Non-blocking. This method never waits for data. It maps runtime scenarios to return
        values:
        - NEXT_EVENT_READY: An event is available now -> returns an Event
        - WAITING_FOR_FUTURE_EVENTS: No event is ready yet -> returns None and is_finished() is False
        - FINISHED: Feed will never produce more -> returns None and is_finished() is True

        After the feed is finished, next() continues to return None.

        Returns:
            Optional[Event]: The next event if it is ready, otherwise None.

        Raises:
            Exception: Implementations should raise on unexpected errors instead of hiding them.
        """
        ...

    def is_finished(self) -> bool:
        """Tell whether this feed will never produce more events.

        Semantics:
        - FINISHED: Returns True when the feed will not produce any more events.
        - Not finished: Returns False; you may poll next() again later.

        Typical behavior:
        - Historical feeds: True after all historical events are delivered.
        - Live feeds: Usually False until the underlying source is permanently closed or exhausted.
        - Timer or scheduled feeds: True after the last scheduled event.

        Performance:
        - Must be fast, non-blocking, and safe to call frequently by the engine.

        Returns:
            bool: True if finished; False otherwise.

        Raises:
            Exception: Implementations should raise on unexpected internal errors.
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

    @property
    def request_info(self) -> dict:
        """Get the original request information that created this feed.

        Contains the metadata from the original request that was used to create this EventFeed.
        This allows the feed to be self-contained with its creation context.

        Returns:
            dict: Contains 'event_type', 'parameters', 'callback', 'event_feed_provider_ref'
        """
        ...
