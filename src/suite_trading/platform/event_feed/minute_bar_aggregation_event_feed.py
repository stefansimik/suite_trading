from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Deque, Optional
import logging
from dataclasses import dataclass

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.utils.datetime_utils import require_utc, format_dt


logger = logging.getLogger(__name__)


@dataclass
class Accumulator:
    """Collect O/H/L/C/Volume across a window and build an aggregated Bar."""

    start_dt: Optional[datetime] = None
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Decimal = Decimal("0")

    def start(self, start_dt: datetime) -> None:
        # Reset values for a new window starting at $start_dt
        self.start_dt = start_dt
        self.open = None
        self.high = None
        self.low = None
        self.close = None
        self.volume = Decimal("0")

    def add(self, bar: Bar) -> None:
        # Accumulate bar into O/H/L/C/Volume
        if self.open is None:
            self.open = bar.open
            self.high = bar.high
            self.low = bar.low
            self.close = bar.close
        else:
            self.high = bar.high if bar.high > self.high else self.high
            self.low = bar.low if bar.low < self.low else self.low
            self.close = bar.close
        if bar.volume is not None:
            self.volume += bar.volume

    def is_empty(self) -> bool:
        return self.open is None

    def to_bar(self, bar_type: BarType, end_dt: datetime) -> Bar:
        return Bar(
            bar_type=bar_type,
            start_dt=self.start_dt,  # type: ignore[arg-type]
            end_dt=end_dt,
            open=self.open,  # type: ignore[arg-type]
            high=self.high,  # type: ignore[arg-type]
            low=self.low,  # type: ignore[arg-type]
            close=self.close,  # type: ignore[arg-type]
            volume=self.volume,
        )


class MinuteBarAggregationEventFeed:
    """Aggregate minute bars into N-minute bars aligned to day boundaries (midnight UTC).

    This EventFeed observes a $source_feed via the listener seam and produces aggregated
    NewBarEvent(s) for N-minute windows where 0 < N < 24*60 and (24*60) % N == 0.

    Policies:
    - First partial window: default is to NOT emit the first partial window. If
      $emit_first_partial is True, the first partial window is emitted when it completes
      (on window advance or equality) or when the source finishes/closes.
    - Gap/no-empty-windows: we never emit empty windows. If the input skips ahead by multiple
      windows, we finalize the current window (if any) and jump to the new window without
      producing events for the missing empty windows.
    """

    # region Init

    def __init__(
        self,
        source_feed: EventFeed,
        window_minutes: int,
        *,  # Forces next params are only keyword args
        emit_first_partial: bool = False,
        callback: Optional[Callable[[Event], None]] = None,
    ) -> None:
        """Initialize the aggregator.

        Args:
            source_feed: EventFeed producing NewBarEvent(s) with Bar.unit == MINUTE.
            window_minutes: Target minute window; 0 < window_minutes < 24*60 and (24*60) % window_minutes == 0.
            callback: Optional function called after this feed's `pop()` returns an event.
            metadata: Optional metadata dict added to aggregated events.
            emit_first_partial: If True, emit the first partial window when it completes or
                on source finish. Otherwise, do not emit the first partial window.

        Raises:
            ValueError: If $window_minutes is unsupported.
        """
        if not isinstance(window_minutes, int) or window_minutes <= 0 or window_minutes >= 24 * 60 or ((24 * 60) % window_minutes != 0):
            raise ValueError(f"Cannot call `MinuteBarAggregationEventFeed.__init__` because $window_minutes ('{window_minutes}') is not supported; use minute values where (24*60) % window_minutes == 0 and window_minutes < (24*60).")

        self._source: EventFeed = source_feed
        self._window_minutes: int = window_minutes
        self._callback: Optional[Callable[[Event], None]] = callback
        self._emit_first_partial: bool = emit_first_partial

        # Auto-generated listener key
        self._listener_key: str = f"minute-agg-{window_minutes}m-{id(self):x}"

        # Output queue
        self._queue: Deque[NewBarEvent] = deque()

        # Registered listeners notified on each successful pop()
        self._listeners: dict[str, Callable[[Event], None]] = {}

        # Accumulator state for the current window
        self._window_end: Optional[datetime] = None
        self._acc: Accumulator = Accumulator()
        self._last_dt_received: Optional[datetime] = None
        self._last_is_historical: Optional[bool] = None

        # Source/target typing
        self._src_minutes: Optional[int] = None
        self._target_bar_type: Optional[BarType] = None

        # First partial window policy tracking
        self._saw_first_window: bool = False
        self._emitted_first_window: bool = False

        # Closed flag
        self._closed: bool = False

        # Subscribe to source
        self._source.add_listener(self._listener_key, self.on_source_event)

    # endregion

    # region Listener

    def on_source_event(self, event: Event) -> None:
        """Handle source events, aggregating NewBarEvent(s) into N-minute bars.

        Raises:
            ValueError: On unsupported event types or incompatible source timeframe.
        """
        # If closed, ignore events
        if self._closed:
            return

        if not isinstance(event, NewBarEvent):
            raise ValueError(f"Cannot call `MinuteBarAggregationEventFeed.on_source_event` because event type '{type(event).__name__}' is not supported; expected NewBarEvent.")

        bar: Bar = event.bar
        bar_type: BarType = bar.bar_type

        # Validate and prepare target BarType; keep on_source_event linear
        self._ensure_target_bar_type(bar_type)

        # Align to right-closed N-minute window (no empty-window emission policy)
        window_start, window_end = self._align_right_closed_window(bar.end_dt)

        # Roll window if needed (finalizes current and starts a new accumulator)
        self._roll_window_if_needed(window_start, window_end)

        # Accumulate current bar
        self._acc.add(bar)

        # Update event attributes for downstream aggregated event
        self._last_dt_received = event.dt_received
        self._last_is_historical = event.is_historical

        # Check: if bar ends exactly at window_end, finalize now
        if self._window_end is not None and bar.end_dt == self._window_end:
            self._finalize_current_window(allow_first_partial=self._emit_first_partial)
            # Prepare next window anchor; accumulator restarts upon next bar
            self._acc.start(self._window_end)
            self._window_end = self._window_end + timedelta(minutes=self._window_minutes)

    # endregion

    # region EventFeed API

    def peek(self) -> Optional[Event]:
        """Return the next aggregated event without consuming it, or None if none is ready."""
        # If source is finished and we have a first-window partial to emit, finalize now
        self._maybe_emit_first_partial("finish")
        if not self._queue:
            return None
        return self._queue[0]

    def pop(self) -> Optional[Event]:
        """Return the next aggregated event and advance this feed, or None if none is ready."""
        # If source is finished and we have a first-window partial to emit, finalize now
        self._maybe_emit_first_partial("finish")
        if not self._queue:
            return None
        next_event = self._queue.popleft()
        # Notify listeners (catch/log and continue)
        if self._listeners:
            for key, listener_fn in list(self._listeners.items()):
                try:
                    listener_fn(next_event)
                except Exception as exc:
                    logger.error(f"Error notifying listener '{key}' for EventFeed (class {self.__class__.__name__}): {exc}")
        # Call optional callback after listeners
        if self._callback is not None:
            try:
                self._callback(next_event)
            except Exception as exc:
                logger.error(f"Error in callback for EventFeed (class {self.__class__.__name__}): {exc}")
        return next_event

    def is_finished(self) -> bool:
        """True when source is finished and no aggregated events remain to be emitted."""
        self._maybe_emit_first_partial("finish")
        return self._source.is_finished() and not self._queue

    # region Observe consumption

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
        """Unregister listener under $key.

        Raises:
            ValueError: If $key is unknown.
        """
        if key not in self._listeners:
            raise ValueError(f"Cannot call `remove_listener` because $key ('{key}') is unknown. Ensure you registered the listener before removing it.")
        del self._listeners[key]

    # endregion

    @property
    def window_minutes(self) -> int:
        """Target window size in minutes.

        Returns:
            int: The N in N-minute aggregation.
        """
        return self._window_minutes

    @property
    def target_bar_type(self) -> Optional[BarType]:
        """The aggregated BarType once known (after first event)."""
        return self._target_bar_type

    @property
    def queue_size(self) -> int:
        """Number of aggregated events waiting to be consumed."""
        return len(self._queue)

    def close(self) -> None:
        """Release resources and unsubscribe. Idempotent."""
        if self._closed:
            return
        # Emit first partial on close if requested and not already emitted
        self._maybe_emit_first_partial("close")
        try:
            self._source.remove_listener(self._listener_key)
        except Exception as exc:
            # Listener might already be removed; log and continue
            logger.debug(f"Close attempted to remove listener '{self._listener_key}' for EventFeed (class {self.__class__.__name__}) and got: {exc}")
        self._queue.clear()
        self._closed = True

    def remove_events_before(self, cutoff_time: datetime) -> None:
        """Remove all aggregated events before $cutoff_time and drop obsolete accumulator."""
        require_utc(cutoff_time)
        # Drop queued outputs older than cutoff
        while self._queue and self._queue[0].dt_event < cutoff_time:
            self._queue.popleft()
        # If current window already ended before/equal cutoff, drop accumulator; also mark first window emitted
        if self._window_end is not None and self._window_end <= cutoff_time:
            # Replace accumulator with a fresh one to drop partial state
            self._acc = Accumulator()
            self._last_dt_received = None
            self._last_is_historical = None
            if not self._emitted_first_window and self._saw_first_window:
                self._emitted_first_window = True

    # endregion

    # region Helpers

    def _roll_window_if_needed(self, window_start: datetime, window_end: datetime) -> None:
        """Advance to $window_end if needed and manage accumulator lifecycle.

        Policy: We do not emit empty windows. If the input skips ahead, we finalize the current
        window (if any) and jump to the new window, leaving gaps with no event.
        """
        # Check: first window initialization
        if self._window_end is None:
            self._window_end = window_end
            self._acc.start(window_start)
            self._saw_first_window = True
            return
        # Check: if we moved to a later window, finalize current before switching
        if window_end > self._window_end:
            self._finalize_current_window(allow_first_partial=self._emit_first_partial)
            self._acc.start(window_start)
            self._window_end = window_end

    def _ensure_target_bar_type(self, bar_type: BarType) -> None:
        """Validate source bar type and create/verify target BarType.

        - Ensures unit is MINUTE.
        - On first event: verifies source timeframe is finer than target and divisible,
          and constructs the target BarType preserving instrument and price_type.
        - On subsequent events: verifies instrument and price_type consistency.

        Raises:
            ValueError: If validation fails.
        """
        # Check: unit must be MINUTE for minute aggregation
        if bar_type.unit is not BarUnit.MINUTE:
            raise ValueError("Cannot call `MinuteBarAggregationEventFeed.on_source_event` because source bar unit is not MINUTE.")

        if self._src_minutes is None:
            self._src_minutes = int(bar_type.value)
            # Check source resolution finer than target and divisibility
            if not (self._src_minutes < self._window_minutes and (self._window_minutes % self._src_minutes == 0)):
                raise ValueError(f"Cannot call `MinuteBarAggregationEventFeed.on_source_event` because source timeframe {self._src_minutes}-MINUTE is not finer than target {self._window_minutes}-MINUTE or not an integer multiple.")
            # Build target BarType preserving instrument and price_type
            self._target_bar_type = BarType(bar_type.instrument, self._window_minutes, BarUnit.MINUTE, bar_type.price_type)
        else:
            # Check instrument and price_type consistency
            if self._target_bar_type is not None:
                if bar_type.instrument != self._target_bar_type.instrument:
                    raise ValueError(f"Cannot call `MinuteBarAggregationEventFeed.on_source_event` because source $instrument ('{bar_type.instrument}') changed and does not match target instrument ('{self._target_bar_type.instrument}').")
                if bar_type.price_type != self._target_bar_type.price_type:
                    raise ValueError(f"Cannot call `MinuteBarAggregationEventFeed.on_source_event` because source $price_type ('{bar_type.price_type.name}') changed and does not match target price_type ('{self._target_bar_type.price_type.name}').")

    def _align_right_closed_window(self, end_dt: datetime) -> tuple[datetime, datetime]:
        """Align $end_dt to a right-closed N-minute window anchored to midnight UTC.

        Examples:
        - For N=5 (divides 60): identical result to previous hour-anchored logic.
        - For N=90: windows end at 00:00, 01:30, 03:00, ... relative to midnight UTC.
        """
        # Check: ensure $end_dt is UTC-aware as required project-wide
        require_utc(end_dt)
        # Anchor to start of the UTC day and compute minutes since midnight
        day_start = end_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        minutes_since_midnight = int((end_dt - day_start).total_seconds() // 60)
        # Ceil to nearest multiple of N minutes counted from midnight
        rounded_minutes = ((minutes_since_midnight + self._window_minutes - 1) // self._window_minutes) * self._window_minutes
        window_end = day_start + timedelta(minutes=rounded_minutes)
        window_start = window_end - timedelta(minutes=self._window_minutes)
        return window_start, window_end

    def _select_event_attrs(self) -> tuple[datetime, bool]:
        """Select aggregated event attributes based on last source event.

        Policy:
        - If $last_is_historical is True or None (unknown), treat aggregated event as
          historical and set dt_received to $window_end.
        - If $last_is_historical is False (live), use $last_dt_received if available;
          otherwise fall back to $window_end.

        Returns:
        - tuple[datetime, bool]: (dt_received, is_historical)
        """
        # Check: ensure we have a window end; caller `_finalize_current_window` guards this
        is_hist = bool(self._last_is_historical) if self._last_is_historical is not None else True
        dt_recv = self._window_end if is_hist else (self._last_dt_received or self._window_end)
        return dt_recv, is_hist

    def _finalize_current_window(self, allow_first_partial: bool) -> None:
        """Finalize the current window and enqueue an aggregated event.

        Args:
            allow_first_partial: If True, the first partial window (if currently active)
                is allowed to emit. If False, the first window is marked as emitted
                without producing an event.
        """
        if self._window_end is None or self._acc.is_empty():
            return

        is_first = self._saw_first_window and not self._emitted_first_window
        if is_first and not allow_first_partial:
            self._emitted_first_window = True
            return

        # Build Bar and NewBarEvent using accumulator
        aggregated_bar = self._acc.to_bar(self._target_bar_type, self._window_end)  # type: ignore[arg-type]
        dt_recv, is_hist = self._select_event_attrs()
        require_utc(dt_recv)
        aggregated_event = NewBarEvent(bar=aggregated_bar, dt_received=dt_recv, is_historical=is_hist)
        self._queue.append(aggregated_event)

        if is_first:
            self._emitted_first_window = True

    def _maybe_emit_first_partial(self, context: str) -> None:
        """Emit the first partial window depending on $context and policy.

        Args:
            context: One of {"advance", "finish", "close"} indicating when the check runs.
        """
        if not self._emit_first_partial:
            return
        if self._emitted_first_window or not self._saw_first_window:
            return
        if context == "finish" and not self._source.is_finished():
            return
        # Check: only emit when we have a non-empty accumulator and a window end
        if self._window_end is not None and not self._acc.is_empty():
            self._finalize_current_window(allow_first_partial=True)

    # endregion

    # region String representations

    def __str__(self) -> str:
        queued_count = len(self._queue)
        end_str = format_dt(self._window_end) if self._window_end else "None"
        return f"{self.__class__.__name__}(window_minutes={self._window_minutes}, current_window_end={end_str}, queued={queued_count})"

    def __repr__(self) -> str:
        queued_count = len(self._queue)
        end_str = format_dt(self._window_end) if self._window_end else "None"
        return f"{self.__class__.__name__}(window_minutes={self._window_minutes!r}, listener_key={self._listener_key!r}, current_window_end={end_str!r}, queued={queued_count!r})"

    # endregion
