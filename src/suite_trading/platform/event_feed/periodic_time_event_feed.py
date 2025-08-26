from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Callable
import logging

from suite_trading.domain.event import Event
from suite_trading.platform.event_feed.event_feed import EventFeed  # noqa: F401 (protocol reference)
from suite_trading.utils.datetime_utils import require_utc, format_dt, format_range


logger = logging.getLogger(__name__)


class TimeTickEvent(Event):
    """Time notification produced by PeriodicTimeEventFeed.

    Purpose:
        Represent a scheduled time tick with its official time ($dt_event) and the
        system arrival time ($dt_received). Both must be timezone‑aware UTC.

    Attributes:
        dt_event (datetime): Scheduled tick time (UTC).
        dt_received (datetime): When the event entered the system (UTC).
    """

    def __init__(
        self,
        dt_event: datetime,
        dt_received: datetime,
    ) -> None:
        """Initialize a time tick event.

        Args:
            dt_event (datetime): The scheduled tick time (timezone-aware UTC).
            dt_received (datetime): When the event entered the system (timezone-aware UTC).

        Raises:
            ValueError: If any datetime is not timezone-aware UTC.
        """
        super().__init__(dt_event=dt_event, dt_received=dt_received)

    @property
    def dt_event(self) -> datetime:
        """Get the scheduled tick time (UTC)."""
        return self._dt_event

    @property
    def dt_received(self) -> datetime:
        """Get when the event entered the system (UTC)."""
        return self._dt_received

    # region String representations

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(dt_event={format_dt(self._dt_event)}, dt_received={format_dt(self._dt_received)})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(dt_event={format_dt(self._dt_event)}, dt_received={format_dt(self._dt_received)})"

    # endregion


class PeriodicTimeEventFeed:
    """Emit TimeTickEvent at a fixed interval (on‑the‑fly, non‑blocking).

    Usage:
        Use `peek()` to check readiness and `pop()` to consume. If $end_datetime is set,
        it is inclusive: the tick at exactly $end_datetime may be emitted and then the
        feed is finished. If $end_datetime is None, the feed runs until `close()`.
        Additionally, when $finish_with_feed is provided, this feed stops producing
        events as soon as that EventFeed reports `is_finished() is True`.

    Args:
        start_dt (datetime): First scheduled tick (UTC).
        interval (timedelta): Positive interval between ticks (> 0).
        end_dt (datetime | None): Optional inclusive stop time (UTC).
        metadata (dict | None): Optional feed metadata; defaults to
            {"source_event_feed_name": "periodic-time-feed"}.
        finish_with_feed (EventFeed | None): Another feed to observe; when it finishes,
            this feed marks itself finished (non‑blocking check in `_check_finished_guard`).

    Raises:
        ValueError: If any datetime is not UTC or if $interval is non‑positive.
    """

    # region Init

    def __init__(
        self,
        start_dt: datetime,
        interval: timedelta,
        end_dt: Optional[datetime] = None,
        finish_with_feed: Optional[EventFeed] = None,
    ) -> None:
        # Check: $start_datetime must be timezone-aware UTC to avoid ambiguous scheduling
        require_utc(start_dt)

        # Check: $interval must be a timedelta to enforce an unambiguous schedule unit
        if not isinstance(interval, timedelta):
            raise ValueError("Cannot call `PeriodicTimeEventFeed.__init__` because $interval is not timedelta.")

        # Check: $interval must be > 0 to make forward progress
        if interval <= timedelta(0):
            raise ValueError("Cannot call `PeriodicTimeEventFeed.__init__` because $interval is non-positive.")

        # Check: $end_datetime (when provided) must be UTC and >= $start_datetime
        if end_dt is not None:
            require_utc(end_dt)
            if end_dt < start_dt:
                raise ValueError("Cannot call `PeriodicTimeEventFeed.__init__` because $end_datetime < $start_datetime.")

        # Copy input params
        self._start_dt: datetime = start_dt
        self._interval: timedelta = interval
        self._end_dt: Optional[datetime] = end_dt
        self._finish_with_feed: Optional[EventFeed] = finish_with_feed

        # Internal state
        self._next_tick_dt: datetime = start_dt
        self._next_event: Optional[TimeTickEvent] = None
        self._closed: bool = False
        self._finished: bool = False

        # Listeners of this event-feed (in case some other objects needs to be notified about consumed/popped events)
        self._listeners: dict[str, Callable[[Event], None]] = {}

    # endregion

    # region EventFeed protocol

    def peek(self) -> Optional[Event]:
        """Return the next event if ready, else None.

        Non-blocking readiness check. When `datetime.now(UTC) >= $next_tick`, a TimeTickEvent is
        created and cached until consumed with `pop()`.

        Returns:
            Optional[Event]: The next TimeTickEvent when ready; otherwise None.
        """
        if self._check_finished_guard():
            return None

        if self._next_event is not None:
            return self._next_event

        # Generate events on-the-fly when wall-clock reaches $next_tick; never pre-buffer
        now = datetime.now(timezone.utc)
        if now < self._next_tick_dt:  # Not yet time for next tick
            return None

        # Generate next event
        self._next_event = TimeTickEvent(dt_event=self._next_tick_dt, dt_received=self._next_tick_dt)

        return self._next_event

    def pop(self) -> Optional[Event]:
        """Return the next event and advance the schedule, or None if not ready.

        Advancing increments $next_tick by $interval. If an inclusive $end_datetime is set and
        the next scheduled tick moves beyond it, the feed is marked finished.

        Returns:
            Optional[Event]: The ready event, or None when not ready.
        """
        if self._check_finished_guard():
            return None

        event = self.peek()
        if event is None:
            return None

        # Consume cached event and advance schedule
        self._next_event = None
        self._next_tick_dt = self._next_tick_dt + self._interval

        # Mark feed as finished, if beyond end_dt
        if self._end_dt is not None and self._next_tick_dt > self._end_dt:
            self._finished = True

        # Notify listeners (catch/log and continue)
        if self._listeners:
            for k, fn in list(self._listeners.items()):
                try:
                    fn(event)
                except Exception as e:
                    logger.error(f"Error in listener '{k}' for PeriodicTimeEventFeed: {e}")

        return event

    def is_finished(self) -> bool:
        """True when the feed will not produce any more events.

        This is True after the inclusive $end_datetime has been passed or after `close()`.

        Returns:
            bool: Finished state flag.
        """
        return self._finished or self._closed

    def close(self) -> None:
        """Release resources used by this feed (idempotent, non-blocking)."""
        self._next_event = None
        self._finished = True
        self._closed = True

    def remove_events_before(self, cutoff_time: datetime) -> None:
        """Advance internal schedule to the first tick >= $cutoff_time.

        For bounded feeds with an inclusive $end_datetime, advancing beyond the end marks the
        feed finished.

        Args:
            cutoff_time (datetime): Events with dt_event before this time will be skipped (UTC).

        Raises:
            ValueError: If $cutoff_time is not timezone-aware UTC.
        """
        # Check: $cutoff_time must be timezone-aware UTC to preserve consistent ordering
        require_utc(cutoff_time)

        if self._closed or self._finished:
            return

        if self._end_dt is not None and cutoff_time > self._end_dt:
            # Jumping beyond the configured range finishes the feed immediately
            self._finished = True
            self._next_event = None
            return

        if self._next_tick_dt >= cutoff_time:
            return

        # Compute how many intervals to jump, rounding up to reach first tick >= $cutoff_time
        delta = cutoff_time - self._next_tick_dt
        step_s = self._interval.total_seconds()
        steps_float = delta.total_seconds() / step_s
        steps = int(steps_float) if steps_float.is_integer() else int(steps_float) + 1
        self._next_tick_dt = self._next_tick_dt + steps * self._interval
        self._next_event = None

        if self._end_dt is not None and self._next_tick_dt > self._end_dt:
            self._finished = True

    # endregion

    # region Observe consumed events

    def add_listener(self, key: str, listener: Callable[[Event], None]) -> None:
        """Register $listener under $key. Called after each successful `pop`.

        Args:
            key: Unique, non-empty identifier for this listener.
            listener: Callable that accepts the consumed Event.

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

        Args:
            key: Identifier of the listener to remove.

        Raises:
            ValueError: If $key is unknown.
        """
        if key not in self._listeners:
            raise ValueError(f"Cannot call `remove_listener` because $key ('{key}') is unknown. Ensure you registered the listener before removing it.")

        del self._listeners[key]

    # endregion

    # region Internal

    def _check_finished_guard(self) -> bool:
        """Return True if the feed cannot produce more events (closed or finished).

        If $end_datetime is configured and the scheduled $next_tick moved beyond it, mark the
        feed as finished.
        """
        if self._closed or self._finished:
            return True

        # Auto-finish this feed - in sync with other feed (if configured).
        if self._finish_with_feed is not None and self._finish_with_feed.is_finished():
            self._finished = True
            return True

        # Auto-finish when next tick exceeds the configured end boundary
        if (self._end_dt is not None) and (self._next_tick_dt > self._end_dt):
            self._finished = True
            return True

        return False

    # endregion

    # region String representations
    def __str__(self) -> str:
        if self._end_dt is not None:
            start_end_range_str = format_range(self._start_dt, self._end_dt)
            return f"{self.__class__.__name__}(range={start_end_range_str}, interval={self._interval}, next_tick={format_dt(self._next_tick_dt)}, finished={self._finished}, closed={self._closed})"
        return f"{self.__class__.__name__}(start={format_dt(self._start_dt)}, interval={self._interval}, next_tick={format_dt(self._next_tick_dt)}, finished={self._finished}, closed={self._closed})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(start={format_dt(self._start_dt)}, end={(format_dt(self._end_dt) if self._end_dt is not None else None)!r}, interval={self._interval!r}, next_tick={format_dt(self._next_tick_dt)}, finished={self._finished!r}, closed={self._closed!r})"

    # endregion
