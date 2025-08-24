from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Deque, Optional
import logging

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.utils.datetime_utils import require_utc, format_dt


logger = logging.getLogger(__name__)


class MinuteBarAggregationEventFeed:
    """Aggregate minute bars into N-minute bars aligned to hour boundaries.

    This EventFeed observes a $source_feed via the listener seam and produces aggregated
    NewBarEvent(s) for N-minute windows where 0 < N < 60 and 60 % N == 0.

    Only one edge-case policy is implemented: the first partial window handling.
    - Default: do not emit the first partial window (emit_first_partial=False)
    - If emit_first_partial=True: emit the first partial window when it completes (on window
      advance) or when the source finishes.
    """

    # region Init

    def __init__(
        self,
        source_feed: EventFeed,
        window_minutes: int,
        *,  # Forces next params are only keyword args
        emit_first_partial: bool = False,
        callback: Optional[Callable[[Event], None]] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """Initialize the aggregator.

        Args:
            source_feed: EventFeed producing NewBarEvent(s) with Bar.unit == MINUTE.
            window_minutes: Target minute window size; must satisfy 0 < window_minutes < 60 and 60 % window_minutes == 0.
            callback: Optional function called after this feed's `pop()` returns an event.
            metadata: Optional metadata dict added to aggregated events.
            emit_first_partial: If True, emit the first partial window when it completes or
                on source finish. Otherwise, do not emit the first partial window.

        Raises:
            ValueError: If $window_minutes is unsupported.
        """
        if not isinstance(window_minutes, int) or window_minutes <= 0 or window_minutes >= 60 or (60 % window_minutes != 0):
            raise ValueError(f"Cannot call `MinuteBarAggregationEventFeed.__init__` because $window_minutes ('{window_minutes}') is not supported; use minute values where 60 % window_minutes == 0 and window_minutes < 60.")

        self._source: EventFeed = source_feed
        self._window_minutes: int = window_minutes
        self._callback: Optional[Callable[[Event], None]] = callback
        self._metadata: Optional[dict] = metadata
        self._emit_first_partial: bool = emit_first_partial

        # Auto-generated listener key for readable diagnostics
        self._listener_key: str = f"minute-agg-{window_minutes}m-{id(self)}"

        # Output queue
        self._queue: Deque[NewBarEvent] = deque()

        # Registered listeners notified on each successful pop()
        self._listeners: dict[str, Callable[[Event], None]] = {}

        # Accumulator state for the current window
        self._current_window_end: Optional[datetime] = None
        self._acc_open: Optional[Decimal] = None
        self._acc_high: Optional[Decimal] = None
        self._acc_low: Optional[Decimal] = None
        self._acc_close: Optional[Decimal] = None
        self._acc_volume: Decimal = Decimal("0")
        self._acc_start_dt: Optional[datetime] = None
        self._last_dt_received: Optional[datetime] = None
        self._last_is_historical: Optional[bool] = None

        # Source/target typing
        self._src_minutes: Optional[int] = None
        self._target_bar_type: Optional[BarType] = None

        # First partial window policy tracking
        self._first_window_seen: bool = False
        self._first_window_emitted: bool = False

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

        # Align current bar to N-minute window with right-closed semantics
        window_start, window_end = self._align_window_right_closed(bar.end_dt)

        # Initialize accumulator if needed
        if self._current_window_end is None:
            self._current_window_end = window_end
            self._acc_start_dt = window_start
            self._first_window_seen = True

        # If we moved to a later window, finalize previous
        if window_end > self._current_window_end:
            self._finalize_current_window()
            self._acc_start_dt = window_start
            self._current_window_end = window_end
            # Reset accumulator values for the new window
            self._reset_accumulator()

        # Accumulate this bar into current window
        if self._acc_open is None:
            self._acc_open = bar.open
            self._acc_high = bar.high
            self._acc_low = bar.low
            self._acc_close = bar.close
        else:
            self._acc_high = bar.high if bar.high > self._acc_high else self._acc_high
            self._acc_low = bar.low if bar.low < self._acc_low else self._acc_low
            self._acc_close = bar.close
        if bar.volume is not None:
            self._acc_volume += bar.volume

        self._last_dt_received = event.dt_received
        self._last_is_historical = event.is_historical

        # If this bar ended exactly at the current window end, finalize now
        if self._current_window_end is not None and bar.end_dt == self._current_window_end:
            self._finalize_current_window()
            # Prepare next window accumulator
            self._acc_start_dt = self._current_window_end
            self._current_window_end = self._current_window_end + timedelta(minutes=self._window_minutes)
            self._reset_accumulator()

    # endregion

    # region EventFeed API

    def peek(self) -> Optional[Event]:
        """Return the next aggregated event without consuming it, or None if none is ready."""
        # If source is finished and we have a first-window partial to emit, finalize now
        self._emit_first_partial_if_needed_on_finish()
        if not self._queue:
            return None
        return self._queue[0]

    def pop(self) -> Optional[Event]:
        """Return the next aggregated event and advance this feed, or None if none is ready."""
        # If source is finished and we have a first-window partial to emit, finalize now
        self._emit_first_partial_if_needed_on_finish()
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
        self._emit_first_partial_if_needed_on_finish()
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
    def metadata(self) -> Optional[dict]:
        """Optional metadata describing this feed."""
        return self._metadata

    def close(self) -> None:
        """Release resources and unsubscribe. Idempotent."""
        if self._closed:
            return
        # Emit first partial on close if requested and not already emitted
        self._emit_first_partial_if_needed(force=True)
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
        if self._current_window_end is not None and self._current_window_end <= cutoff_time:
            self._acc_open = None
            self._acc_high = None
            self._acc_low = None
            self._acc_close = None
            self._acc_volume = Decimal("0")
            self._acc_start_dt = None
            self._last_dt_received = None
            self._last_is_historical = None
            if not self._first_window_emitted and self._first_window_seen:
                self._first_window_emitted = True

    # endregion

    # region Helpers

    def _reset_accumulator(self) -> None:
        """Reset accumulator state for the current window (except $acc_start_dt).

        Keeps the lifecycle DRY and consistent across window transitions and closures.
        """
        self._acc_open = None
        self._acc_high = None
        self._acc_low = None
        self._acc_close = None
        self._acc_volume = Decimal("0")
        self._last_dt_received = None
        self._last_is_historical = None

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

    def _align_window_right_closed(self, end_dt: datetime) -> tuple[datetime, datetime]:
        """Align $end_dt to a right-closed N-minute window on the hour boundary.

        Example for N=5:
        - 10:00 maps to window [09:55, 10:00]
        - 10:07 maps to window [10:05, 10:10]
        """
        # Check: ensure $end_dt is UTC-aware as required project-wide
        require_utc(end_dt)
        hour_start = end_dt.replace(minute=0, second=0, microsecond=0)
        minute = end_dt.minute
        # Ceil to the nearest multiple of N minutes within the hour (minute=0 -> 0)
        rounded = ((minute + self._window_minutes - 1) // self._window_minutes) * self._window_minutes
        window_end = hour_start + timedelta(minutes=rounded)
        window_start = window_end - timedelta(minutes=self._window_minutes)
        return window_start, window_end

    def _select_event_attrs(self) -> tuple[datetime, bool]:
        """Select aggregated event attributes based on last source event.

        Policy:
        - If $last_is_historical is True or None (unknown), treat aggregated event as historical
          and set dt_received to $current_window_end.
        - If $last_is_historical is False (live), use $last_dt_received if available; otherwise
          fall back to $current_window_end.

        Returns:
        - tuple[datetime, bool]: (dt_received, is_historical)
        """
        # Check: ensure we have a window end; caller `_finalize_current_window` guards this
        is_hist = bool(self._last_is_historical) if self._last_is_historical is not None else True
        dt_recv = self._current_window_end if is_hist else (self._last_dt_received or self._current_window_end)
        # mypy: both branches guarantee non-None due to guard in finalize
        return dt_recv, is_hist

    def _finalize_current_window(self) -> None:
        """Finalize the current window and enqueue depending on first-partial policy."""
        if self._current_window_end is None or self._acc_open is None:
            return

        # Decide whether to enqueue based on first-partial policy
        is_first_window = self._first_window_seen and not self._first_window_emitted
        if is_first_window and not self._emit_first_partial:
            # Skip emitting the first partial window
            self._first_window_emitted = True
            return

        # Build Bar and NewBarEvent
        aggregated_bar = Bar(
            bar_type=self._target_bar_type,  # type: ignore[arg-type]
            start_dt=self._acc_start_dt,  # type: ignore[arg-type]
            end_dt=self._current_window_end,
            open=self._acc_open,  # type: ignore[arg-type]
            high=self._acc_high,  # type: ignore[arg-type]
            low=self._acc_low,  # type: ignore[arg-type]
            close=self._acc_close,  # type: ignore[arg-type]
            volume=self._acc_volume,
        )
        # Historical flag and dt_received policies via helper
        dt_recv, is_hist = self._select_event_attrs()
        aggregated_event = NewBarEvent(bar=aggregated_bar, dt_received=dt_recv, is_historical=is_hist, metadata=self._metadata)
        self._queue.append(aggregated_event)

        if is_first_window:
            self._first_window_emitted = True

    def _emit_first_partial_if_needed_on_finish(self) -> None:
        """If the source is finished, emit the first partial window once when requested."""
        if not self._emit_first_partial:
            return
        if self._first_window_emitted or not self._first_window_seen:
            return
        if not self._source.is_finished():
            return
        # If we have an unfinalized first window (no advancement yet), finalize it now
        if self._current_window_end is not None and self._acc_open is not None:
            self._finalize_current_window()

    def _emit_first_partial_if_needed(self, force: bool = False) -> None:
        """Emit first partial if requested and not yet emitted; used on close()."""
        if not self._emit_first_partial:
            return
        if self._first_window_emitted or not self._first_window_seen:
            return
        if force and self._current_window_end is not None and self._acc_open is not None:
            self._finalize_current_window()

    # endregion

    # region String representations

    def __str__(self) -> str:
        queued_count = len(self._queue)
        end_str = format_dt(self._current_window_end) if self._current_window_end else "None"
        return f"{self.__class__.__name__}(window_minutes={self._window_minutes}, current_window_end={end_str}, queued={queued_count})"

    def __repr__(self) -> str:
        queued_count = len(self._queue)
        end_str = format_dt(self._current_window_end) if self._current_window_end else "None"
        return f"{self.__class__.__name__}(window_minutes={self._window_minutes!r}, listener_key={self._listener_key!r}, current_window_end={end_str!r}, queued={queued_count!r}, metadata={self._metadata!r})"

    # endregion
