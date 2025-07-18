from typing import Protocol, Optional
from suite_trading.domain.event import Event


class EventFeed(Protocol):
    """Simple way to get events from different sources.

    EventFeed is technical abstraction, that lets you get events (or data) from anywhere - historical data files, live market
    feeds, scheduled timers, etc. It's designed to be super simple to use while still
    being fast when you have lots of event sources.

    Every EventFeed provides both event access and resource management.
    Simple feeds that don't need connections can implement no-op methods.

    How it works:
    - Call next() to get an event, or None if nothing is ready
    - Call is_finished() to see if this source is completely done (and you can stop using it)
    - Call connect() to establish connection to data source if needed
    - Call disconnect() to clean up resources when done
    - Call is_connected() to check connection status
    - No exceptions to worry about - just simple None checks
    - Same simple pattern works for everything

    Usage Pattern:
        # Simple way to get events
        event = feed.next()
        if event is not None:
            process_event(event)

        # Speed up by removing feeds that are done
        if feed.is_finished():
            feed.disconnect()  # Clean up resources
            active_feeds.remove(feed)

        # Explicit resource management
        feed.connect()
        try:
            # Use the feed
            pass
        finally:
            feed.disconnect()
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

    def get_event_types(self) -> list[str]:
        """Tell what kinds of events this feed gives you.

        This lets you know what to expect from this feed. The names here should
        match what you'll see in the actual events when you call next().

        Common types you might see:
        - "bar": Price bars (open, high, low, close data)
        - "trade_tick": Individual trades that happened
        - "quote_tick": Bid/ask price updates
        - "one_time_event": Something that happens once at a specific time
        - "periodic_event": Something that happens regularly (like every minute)

        Returns:
            list[str]: List of event type names this feed can give you.
                      These match what you'll see in the events themselves.

        Example:
            # Feed that only gives bars
            return ["bar"]

            # Feed that gives multiple types
            return ["trade_tick", "quote_tick"]
        """
        ...

    def connect(self) -> None:
        """Connect to the data source if needed.

        For feeds that don't need connections (like CSV files or in-memory data),
        this method can be empty or just pass. For feeds that do need connections
        (like databases or live APIs), this should establish the connection.

        Safe to call multiple times - should not reconnect if already connected.

        Example:
            # Simple feed - no real connection needed
            def connect(self) -> None:
                pass

            # Database feed - real connection needed
            def connect(self) -> None:
                if not self._connected:
                    self._connection = sqlite3.connect(self.db_path)
                    self._connected = True
        """
        ...

    def disconnect(self) -> None:
        """Disconnect from the data source and clean up resources.

        For feeds that don't need cleanup, this method can be empty or just pass.
        For feeds with resources (files, database connections, network sockets),
        this should clean up properly.

        Safe to call multiple times - should not error if already disconnected.

        Example:
            # Simple feed - no cleanup needed
            def disconnect(self) -> None:
                pass

            # Database feed - real cleanup needed
            def disconnect(self) -> None:
                if self._connection:
                    self._connection.close()
                    self._connection = None
                    self._connected = False
        """
        ...

    def is_connected(self) -> bool:
        """Check if the feed is currently connected to its data source.

        For feeds that don't use connections, this should return True.
        For feeds with actual connections, this should return the real status.

        Returns:
            bool: True if connected/ready, False if disconnected/not ready.

        Example:
            # Simple feed - always ready
            def is_connected(self) -> bool:
                return True

            # Database feed - real connection status
            def is_connected(self) -> bool:
                return self._connection is not None
        """
        ...
