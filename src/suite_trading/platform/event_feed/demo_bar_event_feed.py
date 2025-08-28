from __future__ import annotations

# DemoBarEventFeed: In-memory, historical bar events using generated demo bars.
# Uses a deque to store remaining events; pop() pops from the left.

from collections import deque
from datetime import datetime
from typing import Callable, Deque, Optional
import logging

from suite_trading.utils.datetime_utils import require_utc

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.utils.data_generation.bars import (
    create_bar_series,
    DEFAULT_FIRST_BAR,
)
from suite_trading.utils.data_generation.price_patterns import zig_zag_function


logger = logging.getLogger(__name__)


class DemoBarEventFeed:
    """Historical, in-memory EventFeed producing NewBarEvent from generated demo bars.

    Non-blocking operations; single-consumer expectation.
    """

    # region Init

    def __init__(
        self,
        first_bar: Bar = DEFAULT_FIRST_BAR,
        num_bars: int = 20,
        price_pattern_func: Callable = zig_zag_function,
    ) -> None:
        """Initialize feed and pre-generate events.

        Args:
            first_bar: The first bar used for series generation. Its BarType determines
                the type of all generated bars in the series.
            num_bars: Number of bars to generate (including the first).
            price_pattern_func: Function generating the price curve.
            metadata: Optional feed-level metadata. If None, defaults to
                {"source_event_feed_name": "demo-bar-feed"}.

        Raises:
            ValueError: If `$num_bars` is invalid or generation fails.
        """
        # Check: $num_bars must be >= 1
        if num_bars is None or num_bars < 1:
            raise ValueError(f"Cannot call `DemoBarEventFeed.__init__` because $num_bars ('{num_bars}') is invalid. Provide a value >= 1.")

        # Initialize feed as not closed yet
        self._closed: bool = False

        bars = create_bar_series(
            first_bar=first_bar,
            num_bars=num_bars,
            price_pattern_func=price_pattern_func,
        )

        # Wrap bars into events; dt_received equals dt_event for deterministic historical data
        self._events: Deque[NewBarEvent] = deque(
            NewBarEvent(
                bar=bar,
                dt_received=bar.end_dt,
                is_historical=True,
            )
            for bar in bars
        )

        # Listeners of this event-feed (in case some other objects needs to be notified about consumed/popped events)
        self._listeners: dict[str, Callable[[Event], None]] = {}

    # endregion

    # region EventFeed protocol

    def peek(self) -> Optional[Event]:
        """Return the next event without consuming it, or None if none is ready."""
        if self._closed or not self._events:
            return None
        return self._events[0]

    def pop(self) -> Optional[Event]:
        """Return the next event and advance the feed, or None if none is ready."""
        if self._closed or not self._events:
            return None

        # Consume event
        event = self._events.popleft()

        # Notify listeners
        if self._listeners:
            for k, fn in list(self._listeners.items()):
                try:
                    fn(event)
                except Exception as e:
                    logger.error(f"Error in listener '{k}' for DemoBarEventFeed: {e}")

        return event

    def is_finished(self) -> bool:
        """True when no more events will be produced."""
        return not self._events

    def close(self) -> None:
        """Release resources (idempotent, non-blocking)."""
        if self._closed:
            return
        # Clear remaining events and mark as closed
        self._events.clear()
        self._closed = True

    def remove_events_before(self, cutoff_time: datetime) -> None:
        """Remove all events before $cutoff_time from this event feed.

        That means all events meeting the condition: event.dt_event < $cutoff_time.

        Args:
            cutoff_time: Events with dt_event before this time will be removed.

        Raises:
            ValueError: If $cutoff_time is not timezone-aware UTC.
        """
        # Check: $cutoff_time must be timezone-aware UTC
        require_utc(cutoff_time)

        if self._closed or not self._events:
            return

        # Remove from the front while events are older than cutoff
        while self._events and self._events[0].dt_event < cutoff_time:
            self._events.popleft()

    def add_listener(self, key: str, listener: Callable[[Event], None]) -> None:
        """Register $listener under $key. Called after each successful `pop`.

        Raises:
            ValueError: If $key is empty or already registered.
        """
        if not key:
            raise ValueError("Cannot call `add_listener` because $key is empty")

        if key in self._listeners:
            raise ValueError(f"Cannot call `add_listener` because $key ('{key}') already exists. Use a unique key or call `remove_listener` first.")

        self._listeners[key] = listener

    def remove_listener(self, key: str) -> None:
        """Unregister listener under $key. Log warning if $key is unknown."""
        if key not in self._listeners:
            logger.warning(f"Attempted to remove unknown listener $key ('{key}') from EventFeed (class {self.__class__.__name__})")
            return
        del self._listeners[key]

    # endregion

    # region String representations

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(remaining={len(self._events)}, closed={self._closed})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(remaining={len(self._events)!r}, closed={self._closed!r})"

    # endregion
