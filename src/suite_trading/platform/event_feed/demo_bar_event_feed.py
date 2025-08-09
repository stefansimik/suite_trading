from __future__ import annotations

# DemoBarEventFeed: In-memory, historical bar events using generated demo bars.
# Uses a deque to store remaining events; pop() pops from the left.

from collections import deque
from datetime import datetime, timezone
from typing import Callable, Deque, Optional

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.utils.data_generation.bars import (
    create_bar_series,
    DEFAULT_FIRST_BAR,
)
from suite_trading.utils.data_generation.price_patterns import zig_zag_function


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
        metadata: Optional[dict] = None,
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
        self._metadata: Optional[dict] = metadata

        bars = create_bar_series(
            first_bar=first_bar,
            num_bars=num_bars,
            price_pattern_func=price_pattern_func,
        )

        # Wrap bars into events; dt_received equals dt_event for deterministic historical data
        self._events: Deque[NewBarEvent] = deque(
            NewBarEvent(
                bar=b,
                dt_received=b.end_dt,
                is_historical=True,
                metadata=self._metadata,
            )
            for b in bars
        )

    # endregion

    # region EventFeed API

    def peek(self) -> Optional[Event]:
        """Return the next event without consuming it, or None if none is ready."""
        if self._closed or not self._events:
            return None
        return self._events[0]

    def pop(self) -> Optional[Event]:
        """Return the next event and advance the feed, or None if none is ready."""
        if self._closed or not self._events:
            return None
        return self._events.popleft()

    def next(self) -> Optional[Event]:
        """Deprecated: use pop(). Temporary shim for compatibility."""
        return self.pop()

    def is_finished(self) -> bool:
        """True when no more events will be produced."""
        return not self._events

    @property
    def metadata(self) -> Optional[dict]:
        """Optional metadata describing this feed."""
        return self._metadata

    def close(self) -> None:
        """Release resources (idempotent, non-blocking)."""
        if self._closed:
            return
        # Clear remaining events and mark as closed
        self._events.clear()
        self._closed = True

    def remove_events_before(self, cutoff_time: datetime) -> int:
        """Remove all events with dt_event < cutoff_time by dropping from the head.

        Args:
            cutoff_time: Events with dt_event before this time will be removed.

        Returns:
            Number of events removed from the remaining queue.

        Raises:
            ValueError: If $cutoff_time is not timezone-aware UTC.
        """
        # Check: $cutoff_time must be timezone-aware UTC
        if cutoff_time.tzinfo is None or cutoff_time.tzinfo.utcoffset(cutoff_time) is None:
            raise ValueError(
                "Cannot call `DemoBarEventFeed.remove_events_before` because $cutoff_time is not timezone-aware. Use UTC-aware datetime.",
            )
        if cutoff_time.tzinfo != timezone.utc:
            raise ValueError(
                "Cannot call `DemoBarEventFeed.remove_events_before` because $cutoff_time "
                f"has tzinfo ('{cutoff_time.tzinfo}') not equal to UTC. Use UTC.",
            )

        if self._closed or not self._events:
            return 0

        removed = 0
        # Remove from the front while events are older than cutoff
        while self._events and self._events[0].dt_event < cutoff_time:
            self._events.popleft()
            removed += 1
        return removed

    # endregion

    # region String representations
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(remaining={len(self._events)}, closed={self._closed})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(remaining={len(self._events)!r}, closed={self._closed!r}, metadata={self._metadata!r})"

    # endregion
