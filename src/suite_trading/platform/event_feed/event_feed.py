from typing import Protocol, Optional
from suite_trading.domain.event import Event


class EventFeed(Protocol):
    """Streaming interface that delivers events (one-by-one, chronologically ordered) to strategies.

    Can be used for feeding both historical and live data from any source - historical data files,
    live market feeds, scheduled timers, etc. The interface is designed to be super simple to use
    while still being fast when you have lots of event sources.

    Every EventFeed provides both event access and resource management. Simple feeds that don't
    need cleanup can implement a no-op close() method.

    How it works:
    - Call next() to get an event, or None if nothing is ready
    - Call is_finished() to see if this source is completely done (and you can stop using it)
    - Call close() to release resources when done
    - No exceptions to worry about - just simple None checks
    - Same simple pattern works for everything

    Usage Pattern:
        # Typical pull loop
        while not feed.is_finished():
            event = feed.next()
            if event is not None:
                process_event(event)
        feed.close()
    """

    def next(self) -> Optional[Event]:
        """Get the next event if there's one ready.

        This is the main way to ask "do you have an event for me?" It returns None
        when there's nothing ready right now. This happens in two situations:
        1. No event is ready at the moment (like waiting for live market data)
        2. The feed ran out of data but isn't completely done yet

        For historical data, you'll get None when all the data has been used up.
        For live feeds, you'll get None when no new events have arrived yet.

        Returns:
            Event: The next event if one is ready, or None if nothing is available.

        Note:
            This never throws errors for normal situations. If something goes wrong,
            it handles it quietly and just returns None.
        """
        ...

    def is_finished(self) -> bool:
        """Check if this feed is completely done.

        A finished feed will never give you any more events, so you can stop asking
        it and remove it from your list. This helps keep things running fast when
        you have many feeds - no point checking feeds that are done.

        What this means for different types:
        - Historical feeds: True when all the data has been used up
        - Live feeds: Always False (they keep running and never finish)
        - Timer feeds: True after the scheduled event happened

        Returns:
            bool: True if this feed is completely done and won't give any more events,
                 False if it might still have events in the future.

        Note:
            This helps speed things up. Make sure your feed can answer this quickly
            since it gets called a lot.
        """
        ...

    def close(self) -> None:
        """Release resources used by this feed.

        This cleanup method must be idempotent and safe to call multiple times.
        For feeds that don't allocate external resources, implement this as a no-op.

        Example:
            # Simple feed - no cleanup needed
            def close(self) -> None:
                pass

            # Database feed - real cleanup needed
            def close(self) -> None:
                if self._connection:
                    self._connection.close()
                    self._connection = None
        """
        ...
