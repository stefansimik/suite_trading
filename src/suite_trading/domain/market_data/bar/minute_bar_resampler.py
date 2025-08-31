from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional, Tuple

from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.utils.datetime_utils import require_utc
from suite_trading.utils.math import ceil_to_multiple
from suite_trading.domain.market_data.bar.new_bar_event_accumulator import NewBarEventAccumulator


class MinuteBarResampler:
    """Resample minute Bars into day-aligned, right-closed N-minute windows.

    Purpose:
        Aggregate incoming `NewBarEvent` objects carrying minute Bars into fixed
        N-minute windows aligned to midnight UTC. Emit a `NewBarEvent` for each
        window when it closes on its boundary or when input jumps to a new window.
        The aggregated Bar includes `is_partial` metadata and the emitted event
        propagates latency from the last included input event.

    Constraints:
        - Input must be minute Bars (BarUnit.MINUTE).
        - $window_minutes must be > 0, < 1440 and divide 1440 (day aligned).
        - $window_minutes must be divisible by the input bar size inferred from
          the first input ($window_minutes % $input_bar_minutes == 0).
        - Always emits on window close or jump; never emits empty windows.

    Args:
        $window_minutes (int): Target window size in minutes.
        $on_emit_callback (Callable[[NewBarEvent], None]): Callback invoked with
            aggregated bar events.
    """

    # region Init

    def __init__(self, *, window_minutes: int, on_emit_callback: Callable[[NewBarEvent], None]) -> None:
        # Store input parameters
        self._window_minutes = self._expect_window_minutes(window_minutes)
        self._emit_event_callback = on_emit_callback

        # Windowing / ordering / source sizing
        self._current_window_bounds: Tuple[Optional[datetime], Optional[datetime]] = (None, None)
        self._last_bar_end_dt: Optional[datetime] = None
        self._input_bar_minutes: Optional[int] = None

        # Per-window accumulator
        self._event_accumulator = NewBarEventAccumulator()

        # Public counters
        self.emitted_bar_count: int = 0

    # endregion

    # region Main

    def add_event(self, event: NewBarEvent) -> None:
        """Consume a `NewBarEvent` and resample it into N-minute aggregated bars.

        Behavior:
        - Enforce ordering and UTC.
        - Infer $input_bar_minutes from the first event and require compatibility.
        - Compute the right-closed, day-aligned window for $event.bar.end_dt.
        - If window changes and accumulator has data, emit previous window (partial/full)
          without including the current event, then reset and continue.
        - Add the current event to the accumulator.
        - If the current Bar ends exactly at $window_end, emit aggregated window (including current).

        Args:
            $event (NewBarEvent): Input event carrying a minute Bar.

        Raises:
            ValueError: On invalid input type, non-UTC times, non-monotonic order,
                non-minute input, incompatible window/source sizes, or BarType mismatch.
        """
        self._validate_event_and_ordering(event)
        if self._input_bar_minutes is None:
            self._validate_first_source_and_compatibility(event)

        bar = event.bar
        window_start, window_end = self._compute_window_bounds(bar.end_dt)
        if self._current_window_bounds == (None, None):
            self._current_window_bounds = (window_start, window_end)

        window_changed = self._current_window_bounds != (window_start, window_end)
        has_data = self._event_accumulator.has_data()

        # Emit previous window on jump (exclude current event)
        should_emit_bar_because_window_changed = window_changed and has_data
        if should_emit_bar_because_window_changed:
            self._emit_window(self._current_window_bounds[0], self._current_window_bounds[1])

        # Acccumulate event
        self._event_accumulator.add(event)

        # If we are exactly at the end of the window, emit including current event
        should_emit_bar_because_bar_end_reached = bar.end_dt == window_end
        if should_emit_bar_because_bar_end_reached:
            self._emit_window(window_start, window_end)

        # Update window/order tracking
        self._current_window_bounds = (window_start, window_end)
        self._last_bar_end_dt = bar.end_dt

    def reset(self) -> None:
        """Reset internal state to the initial, empty configuration.

        Clears the accumulator and window/order tracking so the next `add_event` call
        is treated as the first input.

        Returns:
            None: This function mutates internal state only.
        """
        self._event_accumulator.reset()
        self._current_window_bounds = (None, None)
        self._last_bar_end_dt = None
        self._input_bar_minutes = None
        self.emitted_bar_count = 0

    # endregion

    # region Validations

    def _validate_event_and_ordering(self, event: NewBarEvent) -> None:
        if not isinstance(event, NewBarEvent):
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add_event` because $event (class '{type(event).__name__}') is not a NewBarEvent")

        bar = event.bar
        if self._last_bar_end_dt is not None and bar.end_dt < self._last_bar_end_dt:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add_event` because $bar.end_dt ('{bar.end_dt}') is older than previous input ('{self._last_bar_end_dt}')")

    def _validate_first_source_and_compatibility(self, event: NewBarEvent) -> None:
        # Require minute bars
        bar = event.bar
        if bar.unit != BarUnit.MINUTE:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add_event` because $bar.unit ('{bar.unit}') is not BarUnit.MINUTE; only minute bars are supported")

        # Infer input bar size in minutes
        self._input_bar_minutes = int((bar.end_dt - bar.start_dt).total_seconds() // 60)
        if self._input_bar_minutes <= 0:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add_event` because inferred $input_bar_minutes ('{self._input_bar_minutes}') must be > 0")
        if (self._window_minutes % self._input_bar_minutes) != 0:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add_event` because $window_minutes ('{self._window_minutes}') is not divisible by inferred $input_bar_minutes ('{self._input_bar_minutes}')")

    def _expect_window_minutes(self, window_minutes: int) -> int:
        MINUTES_PER_DAY = 24 * 60

        if not isinstance(window_minutes, int):
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $window_minutes must be an int (minutes).")

        if window_minutes <= 0:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $window_minutes ('{window_minutes}') must be > 0.")

        if window_minutes >= MINUTES_PER_DAY:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $window_minutes ('{window_minutes}') must be < {MINUTES_PER_DAY} (minutes per day).")

        if (MINUTES_PER_DAY % window_minutes) != 0:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.__init__` because $window_minutes ('{window_minutes}') must evenly divide a day (i.e., {MINUTES_PER_DAY} % $window_minutes == 0).")

        return window_minutes

    # endregion

    # region Internal

    def _is_partial(self) -> bool:
        full_window_bar_count = self._window_minutes // self._input_bar_minutes
        return self._event_accumulator.count < full_window_bar_count

    def _emit_window(self, window_start: datetime, window_end: datetime) -> None:
        """Build and emit an aggregated NewBarEvent for the given window bounds.

        Uses the current accumulator state to compute partial/full status and then resets the
        accumulator after emitting.

        Args:
            $window_start (datetime): Inclusive start of the aggregated window.
            $window_end (datetime): Exclusive end (right-closed boundary) of the window.
        """
        # Derive output bar type aligned to target window size
        output_bar_type = self._event_accumulator.first_bar_type.copy(value=self._window_minutes)

        # Build aggregated event from the accumulator's current state
        evt = self._event_accumulator.build_event(
            output_bar_type,
            window_start,
            window_end,
            is_partial=self._is_partial(),
        )

        # Emit, update counters, and reset accumulator
        self._emit_event_callback(evt)
        self.emitted_bar_count += 1
        self._event_accumulator.reset()

    def _compute_window_bounds(self, dt: datetime) -> tuple[datetime, datetime]:
        """Compute right-closed N-minute window aligned to midnight UTC for $dt.

        Args:
            $dt (datetime): Timestamp (UTC) to locate within a window.

        Returns:
            tuple[datetime, datetime]: Tuple of ($window_start, $window_end) that
                contains $dt.

        Raises:
            ValueError: If $dt is not timezone-aware UTC (enforced by `require_utc`).
        """
        require_utc(dt)
        day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        minutes_since_midnight = int((dt - day_start).total_seconds() // 60)
        rounded_minutes = ceil_to_multiple(minutes_since_midnight, self._window_minutes)
        window_end = day_start + timedelta(minutes=rounded_minutes)
        window_start = window_end - timedelta(minutes=self._window_minutes)
        return window_start, window_end

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(window_minutes={self._window_minutes}, emitted_bar_count={self.emitted_bar_count})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(window_minutes={self._window_minutes!r}, emitted_bar_count={self.emitted_bar_count!r})"

    # endregion
