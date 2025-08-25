from __future__ import annotations  # enables lazy evaluation of annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType


class OhlcvAccumulator:
    """Primary purpose: a small, reusable helper used in various places to aggregate
    multiple bars (OHLCV) into a single aggregated Bar over a caller-defined window.

    No timing policy:
    - This class only updates O/H/L/C and sums volume, then constructs the Bar.
    - The caller/user of this class decides when a window starts and ends.

    Why this design:
    - Different systems define windows differently (e.g., clock time, sessions, gaps, custom rules).
      By keeping start/end outside, this helper stays simple, reusable, and easy to test.

    Lifecycle:
    - Call `start_window($start_dt)` to begin a new window and clear prior values.
    - Call `add($bar)` for each source bar in the window.
    - Call `build_bar($bar_type, $end_dt)` to produce the aggregated Bar.
    - Use `has_data()` to check whether any bars have been added in the current window.
    """

    # Current window start time (set by `start_window`)
    def __init__(self) -> None:
        # Current window start time (set by `start_window`)
        self.start_dt: Optional[datetime] = None

        # Running OHLC values and cumulative volume
        self.open: Optional[Decimal] = None
        self.high: Optional[Decimal] = None
        self.low: Optional[Decimal] = None
        self.close: Optional[Decimal] = None
        self.volume: Decimal = Decimal("0")

    def start_window(self, start_dt: datetime) -> None:
        """Start a new accumulation window at $start_dt and clear previous state."""
        # Reset values for a new window starting at $start_dt
        self.start_dt = start_dt
        self.open = None
        self.high = None
        self.low = None
        self.close = None
        self.volume = Decimal("0")

    def add(self, bar: Bar) -> None:
        """Accumulate OHLCV from $bar into the current window."""
        # Check: first bar -> initialize running values
        if self.open is None:
            self.open = bar.open
            self.high = bar.high
            self.low = bar.low
            self.close = bar.close
        else:
            # Update running extremes and last close
            self.high = bar.high if bar.high > self.high else self.high
            self.low = bar.low if bar.low < self.low else self.low
            self.close = bar.close

        # Sum volume when provided
        if bar.volume is not None:
            self.volume += bar.volume

    def has_data(self) -> bool:
        """True if at least one bar has been added since `start_window`."""
        return not self.is_empty()

    def is_empty(self) -> bool:
        """True if no bars have been added since `start_window` (opposite of `has_data`)."""
        return self.open is None

    def build_bar(self, bar_type: BarType, end_dt: datetime) -> Bar:
        """Build the aggregated Bar for the current window ending at $end_dt."""
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
