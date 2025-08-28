from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Callable, Deque, Optional
import logging

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.utils.datetime_utils import require_utc
from suite_trading.domain.market_data.bar.ohlcv_accumulator import OhlcvAccumulator
from suite_trading.utils.math import ceil_to_multiple


logger = logging.getLogger(__name__)


class MinuteBarAggregationEventFeed:
    # region Init

    def __init__(self, source_feed, window_minutes: int, emit_first_partial: bool = False):
        # SET INPUT PARAMETERS
        self._source_feed: EventFeed = source_feed
        self._window_minutes: int = self._expect_window_minutes(window_minutes)
        self._emit_first_partial: bool = emit_first_partial

        # LISTENER IN SOURCE FEED
        # This aggregation event-feed registers itself as a listener on the source feed
        self._listener_key: str = f"minute-agg-{window_minutes}m-{id(self):x}"
        self._source_feed.add_listener(self._listener_key, self.on_source_event)

        # LISTENERS OF THIS FEED (who want to be notified about aggregated bars)
        self._listeners: dict[str, Callable[[Event], None]] = {}

        # LIFECYCLE
        self._closed: bool = False

        # BAR AGGREGATION STATE
        self._aggregated_bars_queue: Deque[NewBarEvent] = deque()  # Aggregated bar events are stored in this queue
        self._ohlcv_accumulator = OhlcvAccumulator()
        self.count_aggregated_bars: int = 0

    # endregion

    # region Listener

    def on_source_event(self, event: Event) -> None:
        """Process an event from the source feed
        and store aggregated bars in the queue.
        """
        # If closed, ignore events
        if self._closed:
            return

        # Check: We are processing NewBarEvent(s). Other events are not expected
        if not isinstance(event, NewBarEvent):
            raise ValueError(f"Cannot call `{self.__class__.__name__}.on_source_event` because $event (class '{type(event).__name__}') is not a NewBarEvent. Register this feed on an EventFeed that produces NewBarEvent(s).")

        # Reusable data
        bar: Bar = event.bar
        bar_window_start, bar_window_end = self._compute_window_bounds(bar.end_dt)

        # If bar belongs to the window bounds -> accumulate bars
        bar_belongs_to_window = (bar.start_dt >= bar_window_start) and (bar.end_dt <= bar_window_end)
        if bar_belongs_to_window:
            self._ohlcv_accumulator.add(bar)

        # If bar is at the end of the window -> emit aggregated bar
        bar_is_at_end_of_window = bar.end_dt == bar_window_end
        if bar_is_at_end_of_window:
            # Get aggregated bar
            aggregated_bar_type = BarType(instrument=bar.bar_type.instrument, value=self._window_minutes, unit=bar.unit, price_type=bar.price_type)
            aggregated_bar = self._ohlcv_accumulator.get_aggregated_bar(aggregated_bar_type, bar_window_start, bar_window_end)

            # Increment count
            self.count_aggregated_bars += 1

            # Check if aggregated bar is partial
            is_partial_bar = self._ohlcv_accumulator.window_start_dt > bar_window_start  # Bar is partial, when aggregation started later than the start of the window
            is_first_aggregated_bar = self.count_aggregated_bars == 1

            # There are 3 conditions, when aggregated bar can be emitted
            should_emit_bar = (
                (not is_partial_bar)  # any non-partial bar can be always emitted
                or (not is_first_aggregated_bar)  # any non-first bar (even partial) can be always emitted
                or (is_first_aggregated_bar and is_partial_bar and self._emit_first_partial)  # first partial bar can be emitted only if allowed by setting in `self._emit_first_partial`
            )
            if should_emit_bar:
                # Emit aggregated bar
                new_bar_event = NewBarEvent(bar=aggregated_bar, dt_received=event.dt_received, is_historical=event.is_historical)
                self._aggregated_bars_queue.append(new_bar_event)
                # Reset accumulator
                self._ohlcv_accumulator.reset()

    # endregion

    # region EventFeed protocol

    def peek(self) -> Optional[Event]:
        """Return the next aggregated event without consuming it, or None if none is ready."""
        # If queue is empty, return None
        if not self._aggregated_bars_queue:
            return None

        # Return leftmost value without consuming it
        return self._aggregated_bars_queue[0]

    def pop(self) -> Optional[Event]:
        """Return the next aggregated event, or None if none is ready."""
        # If queue is empty, return None
        if not self._aggregated_bars_queue:
            return None

        # Consume leftmost value
        next_event = self._aggregated_bars_queue.popleft()

        # Notify listeners (catch/log and continue)
        if self._listeners:
            for key, listener_fn in list(self._listeners.items()):
                try:
                    listener_fn(next_event)
                except Exception as exc:
                    logger.error(f"Error notifying listener '{key}' for EventFeed (class {self.__class__.__name__}): {exc}")

        return next_event

    def is_finished(self) -> bool:
        """True when source is finished and no aggregated events remain to be emitted."""
        source_feed_is_finished = self._source_feed.is_finished()
        no_aggregated_bars_remain = len(self._aggregated_bars_queue) == 0

        this_feed_is_finished = source_feed_is_finished and no_aggregated_bars_remain
        return this_feed_is_finished

    def close(self) -> None:
        """Release resources and unsubscribe. Idempotent."""
        if self._closed:
            return

        # Unregister from source feed
        self._source_feed.remove_listener(self._listener_key)

        # Cleanup data
        self._aggregated_bars_queue.clear()

        # Mark as closed
        self._closed = True

    def remove_events_before(self, cutoff_time: datetime) -> None:
        """Remove all aggregated events before $cutoff_time and drop obsolete accumulator."""
        require_utc(cutoff_time)

        # Remove events older than cutoff
        if self._aggregated_bars_queue:
            while self._aggregated_bars_queue and self._aggregated_bars_queue[0].dt_event < cutoff_time:
                self._aggregated_bars_queue.popleft()

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

    # region Internal

    def _expect_window_minutes(self, window_minutes: int) -> int:
        """Validate $window_minutes for day-aligned N-minute aggregation.

        Args:
            window_minutes: Target window size in minutes.

        Raises:
            ValueError: If $window_minutes is not an int, <= 0, >= MINUTES_PER_DAY, or does not
                evenly divide a day (i.e., 24*60 % N != 0).
        """
        MINUTES_PER_DAY = 24 * 60

        # Validate window size in small, readable steps for clarity and precise error reporting
        if not isinstance(window_minutes, int):
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $window_minutes must be an int (minutes).")
        if window_minutes <= 0:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $window_minutes ('{window_minutes}') must be > 0.")
        if window_minutes >= MINUTES_PER_DAY:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $window_minutes ('{window_minutes}') must be < {MINUTES_PER_DAY} (minutes per day).")
        if (MINUTES_PER_DAY % window_minutes) != 0:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $window_minutes ('{window_minutes}') must evenly divide a day (i.e., {MINUTES_PER_DAY} % $window_minutes == 0).")

        return window_minutes

    def _compute_window_bounds(self, dt: datetime) -> tuple[datetime, datetime]:
        """Compute the right-closed N-minute window that contains $dt.

        Purpose:
        - Snap $dt up (ceil) to the nearest N-minute boundary measured from 00:00 UTC.
        - Return ($window_start, $window_end) where $window_end is that boundary and
          $window_start == $window_end - $window_minutes.

        Args:
            dt (datetime): UTC-aware end time of the source bar used to compute the
                right-closed window bounds. Must be tz-aware (UTC).

        Returns:
            tuple[datetime, datetime]: ($window_start, $window_end).

        Examples:
            - N = 5: Windows end at 00:00, 00:05, 00:10, ... relative to midnight UTC.
            - N = 90: Windows end at 00:00, 01:30, 03:00, ... relative to midnight UTC.
            - Boundary: if dt is exactly on a boundary, that boundary is used
              (right-closed), not the next one.

        Notes:
            - Windows are anchored to midnight UTC because $window_minutes evenly divides a day.
            - Validation of $window_minutes happens in `_expect_day_divisible_window_minutes`.
        """
        # Check: ensure $bar_end_time is UTC-aware as required project-wide
        require_utc(dt)

        # Anchor to the UTC midnight of the same day and compute whole minutes since midnight
        day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        bar_end_minutes_since_midnight = int((dt - day_start).total_seconds() // 60)

        # Ceil to the nearest multiple of N minutes from midnight. If already on a boundary, keep it (right-closed semantics).
        rounded_minutes = ceil_to_multiple(bar_end_minutes_since_midnight, self._window_minutes)

        # Final window bounds
        window_end = day_start + timedelta(minutes=rounded_minutes)
        window_start = window_end - timedelta(minutes=self._window_minutes)
        return window_start, window_end

    # endregion

    # region String representations

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(window_minutes={self._window_minutes}, queued={len(self._aggregated_bars_queue)}, closed={self._closed}, count_aggregated_bars={self.count_aggregated_bars})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(window_minutes={self._window_minutes!r}, queued={len(self._aggregated_bars_queue)!r}, closed={self._closed!r}, count_aggregated_bars={self.count_aggregated_bars!r})"

    # endregion
