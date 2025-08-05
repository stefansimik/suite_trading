from typing import Protocol, Optional
from suite_trading.domain.event import Event


class EventFeed(Protocol):
    """Simple streaming interface that delivers events in chronological order to strategies.

    This protocol is intentionally minimal and non-blocking. It supports three observable runtime
    conditions without exposing a heavy state machine.

    States:
    - READY: An event is immediately available -> next() returns an Event
    - IDLE: No event is ready now, but the feed may produce more later -> next() returns None while
      is_finished() is False
    - FINISHED: The feed will never produce more events -> is_finished() is True

    How to use:
    - Call next() repeatedly to pull available events.
    - If next() returns None, check is_finished():
      - False => the feed is IDLE; keep polling later
      - True  => the feed is FINISHED; stop polling
    - Always call close() once you are done to release resources.

    Example:
        while not feed.is_finished():
            event = feed.next()
            if event is not None:
                process_event(event)
        feed.close()

    Notes:
    - Implementations must be non-blocking in next() and should fail fast on unexpected errors
      (raise exceptions rather than silently ignoring problems).
    - This contract intentionally omits advanced controls such as request_stop() or
      finished_reason(). Add such capabilities only when you truly need them, keeping the core API
      simple.
    """

    def next(self) -> Optional[Event]:
        """Return the next event if one is ready.

        Non-blocking. This method never waits for data. It maps runtime conditions to return
        values:
        - READY: An event is available now -> returns an Event
        - IDLE: No event is ready yet -> returns None and is_finished() is False
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
