from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from suite_trading.indicators.base import BarIndicator

if TYPE_CHECKING:
    from suite_trading.domain.market_data.bar.bar import Bar


class PSAR(BarIndicator):
    """Calculates the Parabolic Stop and Reverse (PSAR).

    Parabolic SAR is a trend-following indicator used to determine price
    direction and potential reversals. It uses an acceleration factor that
    increases as the trend continues.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, acceleration: float = 0.02, acceleration_step: float = 0.02, acceleration_max: float = 0.2, max_history: int = 100):
        """Initializes Parabolic SAR with acceleration parameters.

        Args:
            acceleration: Initial acceleration factor (default 0.02).
            acceleration_step: Increment for acceleration factor (default 0.02).
            acceleration_max: MAX acceleration factor (default 0.2).
            max_history: Number of last calculated values stored.
        """
        super().__init__(max_history)

        self._accel_init = float(acceleration)
        self._accel_step = float(acceleration_step)
        self._accel_max = float(acceleration_max)

        # STATE
        self._af = 0.0
        self._xp = 0.0
        self._long_position = True
        self._af_increased = False

        # We need recent highs and lows for the 'TodaySAR' rule
        self._highs: deque[float] = deque(maxlen=3)
        self._lows: deque[float] = deque(maxlen=3)

        self._last_sar = 0.0

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        super().reset()
        self._af = 0.0
        self._xp = 0.0
        self._long_position = True
        self._af_increased = False
        self._highs.clear()
        self._lows.clear()
        self._last_sar = 0.0

    # endregion

    # region Utilities

    def _calculate(self, bar: Bar) -> float | None:
        """Computes the latest PSAR value."""
        high0 = float(bar.high)
        low0 = float(bar.low)

        self._highs.appendleft(high0)
        self._lows.appendleft(low0)

        # WARMUP (Matches NT logic: needs 4 bars to start)
        if self._update_count < 3:
            return None

        if self._update_count == 3:
            # INITIAL POSITION DETERMINATION
            # NT: longPosition = High[0] > High[1]
            self._long_position = self._highs[0] > self._highs[1]

            # xp = longPosition ? MAX(High, CurrentBar)[0] : MIN(Low, CurrentBar)[0]
            if self._long_position:
                self._xp = max(self._highs)
            else:
                self._xp = min(self._lows)

            self._af = self._accel_init

            # Value[0] = xp + (longPosition ? -1 : 1) * ((MAX(High, CurrentBar)[0] - MIN(Low, CurrentBar)[0]) * af)
            range_val = max(self._highs) - min(self._lows)
            self._last_sar = self._xp + (-1.0 if self._long_position else 1.0) * (range_val * self._af)
        else:
            # MAIN LOGIC
            # Reset accelerator increase limiter on new bars (in our case every update is a new bar)
            self._af_increased = False

            # SAR = SAR[1] + af * (xp - SAR[1])
            today_sar = self._last_sar + self._af * (self._xp - self._last_sar)

            # TodaySAR rule: can't be inside the bar of day-1 or day-2
            if self._long_position:
                # lowestSAR = Math.Min(Math.Min(todaySAR, Low[0]), Low[1])
                # Note: indices in our deque [0]=current, [1]=prev
                lowest_sar = min(today_sar, self._lows[0], self._lows[1])
                if self._lows[0] > lowest_sar:
                    today_sar = lowest_sar
            else:
                # highestSAR = Math.Max(Math.Max(todaySAR, High[0]), High[1])
                highest_sar = max(today_sar, self._highs[0], self._highs[1])
                if self._highs[0] < highest_sar:
                    today_sar = highest_sar

            # Update extreme price (xp) and acceleration factor (af)
            if self._long_position:
                if self._highs[0] > self._xp:
                    self._xp = self._highs[0]
                    self._increase_af()
            else:
                if self._lows[0] < self._xp:
                    self._xp = self._lows[0]
                    self._increase_af()

            # REVERSAL CHECK
            reverse = False
            if self._long_position:
                if self._lows[0] < today_sar or self._lows[1] < today_sar:
                    reverse = True
            else:
                if self._highs[0] > today_sar or self._highs[1] > today_sar:
                    reverse = True

            if reverse:
                # REVERSE POSITION
                self._last_sar = self._xp  # New SAR is previous XP
                self._long_position = not self._long_position
                self._af = self._accel_init
                self._xp = self._highs[0] if self._long_position else self._lows[0]
            else:
                self._last_sar = today_sar

        return self._last_sar

    def _increase_af(self) -> None:
        """Increases the acceleration factor by the step up to the maximum."""
        if not self._af_increased:
            self._af = min(self._accel_max, self._af + self._accel_step)
            self._af_increased = True

    def _build_name(self) -> str:
        result = f"PSAR({self._accel_init}, {self._accel_step}, {self._accel_max})"
        return result

    def _compute_warmup_period(self) -> int:
        # Justification: Parabolic SAR needs 4 bars to initialize
        return 4

    # endregion
