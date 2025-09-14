from collections import deque
from datetime import datetime
from typing import Callable, Deque, Optional
import logging

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.utils.datetime_utils import require_utc
from suite_trading.domain.market_data.bar.time_bar_resampler import TimeBarResampler


logger = logging.getLogger(__name__)


class TimeBarAggregationEventFeed:
    """Aggregate time-based bars from a source EventFeed using `TimeBarResampler`.

    Receive source bars path:
      - `on_source_event`: receives NewBarEvent(s) from $source_feed and forwards to the
        resampler.

    Aggregation path:
      - `on_aggregated_event`: invoked by `TimeBarResampler` when a window closes or updates;
        applies partial-bar policy and enqueues resulting events.

    Consumers pull aggregated events via `peek`/`pop`. External listeners registered with
    `add_listener` are notified by the TradingEngine after successful `pop` calls.
    """

    # region Init

    def __init__(self, source_feed, unit: BarUnit, size: int, emit_first_partial_bar: bool = True, emit_later_partial_bars: bool = True):
        # SET INPUT PARAMETERS
        self._source_feed = source_feed
        self._unit = unit
        self._size = size
        self._emit_first_partial_bar = emit_first_partial_bar
        self._emit_later_partial_bars = emit_later_partial_bars

        # Check: ensure size > 0
        if not isinstance(self._size, int) or self._size <= 0:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $size ('{self._size}') must be > 0")

        # Check: unit must be SECOND/MINUTE/HOUR/DAY
        if self._unit not in {BarUnit.SECOND, BarUnit.MINUTE, BarUnit.HOUR, BarUnit.DAY}:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $unit ('{self._unit}') is not supported; use SECOND, MINUTE, HOUR, or DAY")

        # LISTENERS OF THIS FEED (who want to be notified about aggregated bars)
        self._listeners: dict[str, Callable[[Event], None]] = {}

        # LIFECYCLE
        self._closed: bool = False

        # LISTEN TO SOURCE FEED: This way we listen to receive input events from source-feed
        self._listener_key: str = f"time-agg-{self._unit.name.lower()}-{self._size}-{id(self):x}"
        self._source_feed.add_listener(self._listener_key, self.on_source_event)

        # RESAMPLER: This object generates aggregated events
        self._resampler = TimeBarResampler(unit=self._unit, size=self._size, on_emit_callback=self.on_aggregated_event)

        # AGGREGATED EVENTS
        self._aggregated_event_queue: Deque[NewBarEvent] = deque()  # Aggregated bar events are stored in this queue
        self.emitted_event_count: int = 0

    # endregion

    # region Listener

    def on_source_event(self, event: Event) -> None:
        """Ingest a NewBarEvent from $source_feed and forward to `TimeBarResampler`.

        Args:
            event (Event): Must be a NewBarEvent; otherwise a ValueError is raised.
        """
        # If closed, ignore events
        if self._closed:
            return

        # Check: We are processing NewBarEvent(s). Other events are not expected
        if not isinstance(event, NewBarEvent):
            raise ValueError(f"Cannot call `{self.__class__.__name__}.on_source_event` because $event (class '{type(event).__name__}') is not a NewBarEvent. Register this feed on an EventFeed that produces NewBarEvent(s).")

        # Delegate to resampler which will invoke `on_aggregated_event` on window emissions
        self._resampler.add_event(event)

    # endregion

    # region Resampler callback

    def on_aggregated_event(self, evt: NewBarEvent) -> None:
        """Handle aggregated bar from `TimeBarResampler` and apply partial-bar policy.

        Purpose:
            - Aggregation path: the resampler emits a NewBarEvent for the configured
              (unit,size) window, and this feed decides whether to enqueue it.

        Args:
            evt (NewBarEvent): Aggregated bar event (may be partial).
        """
        is_partial = evt.bar.is_partial
        is_first = self.emitted_event_count == 0

        should_emit = (not is_partial) or (is_partial and is_first and self._emit_first_partial_bar) or (is_partial and (not is_first) and self._emit_later_partial_bars)
        if not should_emit:
            return

        self._aggregated_event_queue.append(evt)
        self.emitted_event_count += 1

    # endregion

    # region EventFeed protocol

    def peek(self) -> Optional[Event]:
        """Return the next aggregated event without consuming it, or None if none is ready."""
        # If queue is empty, return None
        if not self._aggregated_event_queue:
            return None

        # Return leftmost value without consuming it
        return self._aggregated_event_queue[0]

    def pop(self) -> Optional[Event]:
        """Return the next aggregated event, or None if none is ready."""
        # If queue is empty, return None
        if not self._aggregated_event_queue:
            return None

        # Consume leftmost value
        next_event = self._aggregated_event_queue.popleft()

        return next_event

    def is_finished(self) -> bool:
        """True when source is finished and no aggregated events remain to be emitted."""
        source_feed_is_finished = self._source_feed.is_finished()
        no_aggregated_bars_remain = len(self._aggregated_event_queue) == 0

        this_feed_is_finished = source_feed_is_finished and no_aggregated_bars_remain
        return this_feed_is_finished

    def close(self) -> None:
        """Release resources and unsubscribe. Idempotent."""
        if self._closed:
            return

        # Unregister from source feed
        self._source_feed.remove_listener(self._listener_key)

        # Cleanup data
        self._aggregated_event_queue.clear()

        # Mark as closed
        self._closed = True

    def remove_events_before(self, cutoff_time: datetime) -> None:
        """Remove all aggregated events before $cutoff_time and drop obsolete accumulator."""
        require_utc(cutoff_time)

        # Remove events older than cutoff
        if self._aggregated_event_queue:
            while self._aggregated_event_queue and self._aggregated_event_queue[0].dt_event < cutoff_time:
                self._aggregated_event_queue.popleft()

    def add_listener(self, key: str, listener: Callable[[Event], None]) -> None:
        """Register $listener under $key.

        Notes:
            Listeners are invoked by TradingEngine after each successful pop() from this feed.

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

    def get_listeners(self) -> list[Callable[[Event], None]]:
        return list(self._listeners.values())

    # endregion

    # region String representations

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(unit={self._unit.name}, size={self._size}, queued={len(self._aggregated_event_queue)}, closed={self._closed}, emitted_event_count={self.emitted_event_count})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(unit={self._unit!r}, size={self._size!r}, queued={len(self._aggregated_event_queue)!r}, closed={self._closed!r}, emitted_event_count={self.emitted_event_count!r})"

    # endregion
