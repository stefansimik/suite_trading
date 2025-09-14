from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional, Tuple

from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.utils.datetime_utils import require_utc
from suite_trading.utils.math import ceil_to_multiple
from suite_trading.domain.market_data.bar.new_bar_event_accumulator import NewBarEventAccumulator


#
class TimeBarResampler:
    """Resample time-based Bars into right-closed windows of (unit,size).

    Purpose:
        Aggregate incoming `NewBarEvent` objects carrying time-based Bars into fixed
        windows aligned to UTC day boundaries. Emit a `NewBarEvent` for each window when it
        closes on its boundary or when input jumps to a new window. The aggregated Bar
        includes `is_partial` metadata and the emitted event propagates latency from the
        last included input event.

    Constraints (v1):
        - Supported output units: SECOND, MINUTE, HOUR, DAY (daily = 00:00–24:00 UTC, right-closed).
        - If $unit is DAY, only $size == 1 is supported.
        - Input bars must also be time-based with units in {SECOND, MINUTE, HOUR, DAY}.
        - Output window duration must be >= input bar duration and an exact multiple of it.
        - Alignment is anchored to midnight UTC using total seconds since day start.

    Args:
        $unit (BarUnit): Target time unit (SECOND, MINUTE, HOUR, DAY).
        $size (int): Positive integer window size in $unit.
        $on_emit_callback (Callable[[NewBarEvent], None]): Callback invoked with aggregated
            bar events.
    """

    # region Init

    def __init__(self, *, unit: BarUnit, size: int, on_emit_callback: Callable[[NewBarEvent], None]) -> None:
        # Check: size must be > 0
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"Cannot call `TimeBarResampler.__init__` because $size ('{size}') is not > 0")

        # Check: unit supported
        if unit not in {BarUnit.SECOND, BarUnit.MINUTE, BarUnit.HOUR, BarUnit.DAY, BarUnit.WEEK, BarUnit.MONTH}:
            raise ValueError(f"Cannot call `TimeBarResampler.__init__` because $unit ('{unit}') is not supported; use SECOND, MINUTE, HOUR, DAY, WEEK, or MONTH")

        # Check: only size==1 allowed for DAY, WEEK, and MONTH
        if unit in {BarUnit.DAY, BarUnit.WEEK, BarUnit.MONTH} and size != 1:
            raise ValueError(f"Cannot call `TimeBarResampler.__init__` because $unit is {unit.name} but $size ('{size}') is not 1; only {unit.name.lower()} size=1 is supported")

        self._unit = unit
        self._size = size
        self._on_emit = on_emit_callback

        # Windowing / ordering / source sizing
        self._window_bounds: Tuple[Optional[datetime], Optional[datetime]] = (None, None)
        self._last_bar_end_dt: Optional[datetime] = None
        self._input_bar_seconds: Optional[int] = None

        # Per-window accumulator
        self._event_accumulator = NewBarEventAccumulator()

        # Public counters
        self.emitted_bar_count: int = 0

    # endregion

    # region Main logic

    def add_event(self, event: NewBarEvent) -> None:
        """Consume a `NewBarEvent` and resample it into aggregated time bars.

        Behavior:
        - Enforce ordering.
        - Infer $input_bar_seconds from the first event and require compatibility.
        - Compute the right-closed, UTC-aligned window for $event.bar.end_dt.
        - If window changes and accumulator has data, emit previous window (partial/full)
          without including the current event, then reset and continue.
        - Add the current event to the accumulator.
        - If the current Bar ends exactly at $window_end, emit aggregated window (including current).

        Args:
            $event (NewBarEvent): Input event carrying a time-based Bar.
        """
        self._validate_event_and_ordering(event)
        if self._input_bar_seconds is None:
            self._validate_first_source_and_compatibility(event)

        bar = event.bar
        window_start, window_end = self._compute_window_bounds(bar.end_dt)
        if self._window_bounds == (None, None):
            self._window_bounds = (window_start, window_end)

        window_changed = self._window_bounds != (window_start, window_end)
        has_data = self._event_accumulator.has_data()

        # Emit previous window on jump (exclude current event)
        should_emit_bar_because_window_changed = window_changed and has_data
        if should_emit_bar_because_window_changed:
            self._emit_window(self._window_bounds[0], self._window_bounds[1])

        # Accumulate event
        self._event_accumulator.add(event)

        # If we are exactly at the end of the window, emit including current event
        should_emit_bar_because_window_end_reached = bar.end_dt == window_end
        if should_emit_bar_because_window_end_reached:
            self._emit_window(window_start, window_end)

        # Update window/order tracking
        self._window_bounds = (window_start, window_end)
        self._last_bar_end_dt = bar.end_dt

    def reset(self) -> None:
        """Reset internal state to the initial, empty configuration."""
        self._event_accumulator.reset()
        self._window_bounds = (None, None)
        self._last_bar_end_dt = None
        self._input_bar_seconds = None
        self.emitted_bar_count = 0

    # endregion

    # region Validations

    def _validate_event_and_ordering(self, event: NewBarEvent) -> None:
        if not isinstance(event, NewBarEvent):
            raise ValueError(f"Cannot call `TimeBarResampler.add_event` because $event (class '{type(event).__name__}') is not a NewBarEvent")

        bar = event.bar
        if self._last_bar_end_dt is not None and bar.end_dt < self._last_bar_end_dt:
            raise ValueError(f"Cannot call `TimeBarResampler.add_event` because $bar.end_dt ('{bar.end_dt}') is older than previous input ('{self._last_bar_end_dt}')")

    def _validate_first_source_and_compatibility(self, event: NewBarEvent) -> None:
        # Require time-based bars
        bar = event.bar
        if bar.unit not in {BarUnit.SECOND, BarUnit.MINUTE, BarUnit.HOUR, BarUnit.DAY}:
            raise ValueError(f"Cannot call `TimeBarResampler.add_event` because $bar.unit ('{bar.unit}') is not a supported time unit; only SECOND, MINUTE, HOUR, DAY are supported")

        # Infer input bar size in seconds
        self._input_bar_seconds = int((bar.end_dt - bar.start_dt).total_seconds())
        if self._input_bar_seconds <= 0:
            raise ValueError(f"Cannot call `TimeBarResampler.add_event` because inferred $input_bar_seconds ('{self._input_bar_seconds}') must be > 0")

        if self._unit == BarUnit.MONTH:
            # For monthly aggregation: input must evenly divide a day (86400 seconds)
            if 86400 % self._input_bar_seconds != 0:
                raise ValueError(f"Cannot call `TimeBarResampler.add_event` because monthly aggregation requires $input_bar_seconds to divide 86400; got '{self._input_bar_seconds}'")
            # Validate current month window is multiple of input size
            window_start, window_end = self._compute_window_bounds(bar.end_dt)
            month_seconds = int((window_end - window_start).total_seconds())
            if (month_seconds % self._input_bar_seconds) != 0:
                raise ValueError(f"Cannot call `TimeBarResampler.add_event` because current month length in seconds ('{month_seconds}') is not a multiple of $input_bar_seconds ('{self._input_bar_seconds}')")
        else:
            # For SECOND/MINUTE/HOUR/DAY/WEEK the window seconds are fixed; MONTH varies and is handled above
            window_seconds = self._window_seconds()
            # Check: output window not finer than input
            if window_seconds < self._input_bar_seconds:
                raise ValueError(f"Cannot call `TimeBarResampler.add_event` because $output_window_seconds ('{window_seconds}') is < $input_bar_seconds ('{self._input_bar_seconds}')")
            # Check: multiple rule
            if (window_seconds % self._input_bar_seconds) != 0:
                raise ValueError(f"Cannot call `TimeBarResampler.add_event` because $output_window_seconds ('{window_seconds}') is not a multiple of $input_bar_seconds ('{self._input_bar_seconds}')")

    # endregion

    # region Internal

    def _unit_seconds(self) -> int:
        match self._unit:
            case BarUnit.SECOND:
                return 1
            case BarUnit.MINUTE:
                return 60
            case BarUnit.HOUR:
                return 3600
            case BarUnit.DAY:
                return 86400
            case BarUnit.WEEK:
                return 604800
            case _:
                raise ValueError(f"Cannot call `TimeBarResampler._unit_seconds` because $unit ('{self._unit}') is not a fixed-length time unit")

    def _window_seconds(self) -> int:
        return self._size * self._unit_seconds()

    def _is_partial(self) -> bool:
        full_window_bar_count = self._window_seconds() // int(self._input_bar_seconds or 1)
        return self._event_accumulator.count < full_window_bar_count

    def _emit_window(self, window_start: datetime, window_end: datetime) -> None:
        """Build and emit an aggregated NewBarEvent for the given window bounds."""
        # Derive output bar type aligned to target window size
        first_bar_type = self._event_accumulator.first_bar_type
        if first_bar_type is None:
            return
        output_bar_type = first_bar_type.copy(value=self._size, unit=self._unit)

        # Compute partial flag; for MONTH use actual window duration due to variable length
        if self._unit == BarUnit.MONTH:
            full_seconds = int((window_end - window_start).total_seconds())
            full_window_bar_count = full_seconds // int(self._input_bar_seconds or 1)
            is_partial = self._event_accumulator.count < full_window_bar_count
        else:
            is_partial = self._is_partial()

        # Build aggregated event from the accumulator's current state
        aggregated_event = self._event_accumulator.build_event(
            output_bar_type,
            window_start,
            window_end,
            is_partial=is_partial,
        )

        # Emit, update counters, and reset accumulator
        self._on_emit(aggregated_event)
        self.emitted_bar_count += 1
        self._event_accumulator.reset()

    def _compute_window_bounds(self, dt: datetime) -> tuple[datetime, datetime]:
        """Compute right-closed UTC window for $dt.

        Logic:
        - For SECOND/MINUTE/HOUR (and DAY with size=1), align using seconds since midnight and
          round up to the nearest multiple of $window_seconds within the UTC day.
        - For WEEK (size=1), align to calendar week boundaries: Monday 00:00 UTC to next Monday
          00:00 UTC. The end boundary is the smallest Monday >= $dt (i.e., dt exactly at Monday
          00:00 is considered the end of the previous week).
        - For MONTH (size=1), align to calendar months: first day 00:00 UTC to first day 00:00
          next month. An event exactly at month start closes the previous month.
        """
        require_utc(dt)

        if self._unit == BarUnit.MONTH:
            # Compute month window where end is the smallest 1st-of-month 00:00 >= $dt.
            # Subtract 1 microsecond so dt at exact month start maps to previous month.
            dt_adjusted = dt - timedelta(microseconds=1)
            day_start = dt_adjusted.replace(hour=0, minute=0, second=0, microsecond=0)
            month_start = day_start.replace(day=1)
            # Compute next month start (handles Dec -> Jan)
            if month_start.month == 12:
                next_month_start = month_start.replace(year=month_start.year + 1, month=1)
            else:
                next_month_start = month_start.replace(month=month_start.month + 1)
            return month_start, next_month_start

        if self._unit == BarUnit.WEEK:
            # Compute week window where end is the smallest Monday 00:00 >= $dt.
            # We subtract 1 microsecond so that dt exactly at Monday 00:00 maps to the previous
            # week's start when we floor to Monday, making the end equal to the current Monday.
            dt_adjusted = dt - timedelta(microseconds=1)
            day_start = dt_adjusted.replace(hour=0, minute=0, second=0, microsecond=0)
            weekday = day_start.weekday()  # Monday=0 .. Sunday=6
            week_start = day_start - timedelta(days=weekday)
            window_start = week_start
            window_end = week_start + timedelta(days=7)
            return window_start, window_end

        # Default path for SECOND/MINUTE/HOUR and DAY (size=1)
        day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_since_day_start = int((dt - day_start).total_seconds())
        window_seconds = self._window_seconds()
        rounded_seconds = ceil_to_multiple(seconds_since_day_start, window_seconds)
        window_end = day_start + timedelta(seconds=rounded_seconds)
        window_start = window_end - timedelta(seconds=window_seconds)
        return window_start, window_end

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(unit={self._unit.name}, size={self._size}, emitted_bar_count={self.emitted_bar_count})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(unit={self._unit!r}, size={self._size!r}, emitted_bar_count={self.emitted_bar_count!r})"

    # endregion
