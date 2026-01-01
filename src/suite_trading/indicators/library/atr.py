from __future__ import annotations

from typing import TYPE_CHECKING

from suite_trading.indicators.base import BarIndicator

if TYPE_CHECKING:
    from suite_trading.domain.market_data.bar.bar import Bar


class ATR(BarIndicator):
    """Calculates the Average True Range (ATR).

    ATR is a measure of volatility. This implementation uses Wilder's
    smoothing method (recursive formula).
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period: int = 14, max_history: int = 100):
        """Initializes ATR with a specific lookback period.

        Args:
            period: Lookback period for the smoothing.
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `ATR` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        self._last_close: float | None = None
        self._last_atr: float | None = None

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        super().reset()
        self._last_close = None
        self._last_atr = None

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    # endregion

    # region Utilities

    def _calculate(self, bar: Bar) -> float | None:
        """Computes the latest ATR value using Wilder's smoothing."""
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)

        # TRUE RANGE (TR) CALCULATION
        if self._last_close is None:
            # First bar: TR is simply High - Low
            tr = high - low
        else:
            # TR = max(H-L, |H-C_prev|, |L-C_prev|)
            tr = max(high - low, abs(high - self._last_close), abs(low - self._last_close))

        self._last_close = close

        # WILDER'S SMOOTHING
        if self._last_atr is None:
            # INITIALIZATION (Simple average for the first period)
            if self._update_count == 0:
                self._last_atr = tr
            else:
                # Recursive approximation of SMA for initial values
                self._last_atr = (self._last_atr * self._update_count + tr) / (self._update_count + 1)
        else:
            # Formula: ATR_t = ((period - 1) * ATR_prev + TR_t) / period
            self._last_atr = ((self._period - 1) * self._last_atr + tr) / self._period

        # Skip: not enough values for strict warmup
        if self._update_count < self._period - 1:
            return None

        return self._last_atr

    def _build_name(self) -> str:
        result = f"ATR({self._period})"
        return result

    # endregion
