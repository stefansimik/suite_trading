from __future__ import annotations


from suite_trading.indicators.base import BarIndicator

from suite_trading.domain.market_data.bar.bar import Bar


class ADX(BarIndicator):
    """Calculates the Average Directional Index (ADX).

    ADX measures the strength of a prevailing trend. It uses Wilder's
    smoothing for both the Directional Movement components and the final index.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period: int = 14, max_history: int = 100):
        """Initializes ADX with a specific lookback period.

        Args:
            period: Lookback period for the smoothing (default is 14).
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot call `__init__` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        self._last_high: float | None = None
        self._last_low: float | None = None
        self._last_close: float | None = None

        self._sum_tr = 0.0
        self._sum_dm_plus = 0.0
        self._sum_dm_minus = 0.0
        self._last_adx = 50.0

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        super().reset()
        self._last_high = None
        self._last_low = None
        self._last_close = None
        self._sum_tr = 0.0
        self._sum_dm_plus = 0.0
        self._sum_dm_minus = 0.0
        self._last_adx = 50.0

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    # endregion

    # region Utilities

    def _calculate(self, bar: Bar) -> float | None:
        """Computes the latest ADX value."""
        high0 = float(bar.high)
        low0 = float(bar.low)
        close0 = float(bar.close)

        # INITIAL BAR
        if self._last_high is None:
            tr = high0 - low0
            dm_plus = 0.0
            dm_minus = 0.0

            self._sum_tr = tr
            self._sum_dm_plus = dm_plus
            self._sum_dm_minus = dm_minus
            # NT initializes ADX at 50 on the first bar
            self._last_adx = 50.0
        else:
            # TRUE RANGE & DIRECTIONAL MOVEMENT
            tr = max(abs(low0 - self._last_close), high0 - low0, abs(high0 - self._last_close))

            diff_high = high0 - self._last_high
            diff_low = self._last_low - low0

            dm_plus = max(diff_high, 0.0) if diff_high > diff_low else 0.0
            dm_minus = max(diff_low, 0.0) if diff_low > diff_high else 0.0

            # WILDER'S SMOOTHING FOR SUMS
            if self._update_count < self._period:
                self._sum_tr += tr
                self._sum_dm_plus += dm_plus
                self._sum_dm_minus += dm_minus
            else:
                self._sum_tr = self._sum_tr - (self._sum_tr / self._period) + tr
                self._sum_dm_plus = self._sum_dm_plus - (self._sum_dm_plus / self._period) + dm_plus
                self._sum_dm_minus = self._sum_dm_minus - (self._sum_dm_minus / self._period) + dm_minus

        # Calculate ADX based on current sums
        # Note: we use self._update_count to match NT's logic.
        di_plus = 100.0 * (self._sum_dm_plus / self._sum_tr if self._sum_tr != 0 else 0.0)
        di_minus = 100.0 * (self._sum_dm_minus / self._sum_tr if self._sum_tr != 0 else 0.0)

        diff = abs(di_plus - di_minus)
        denom = di_plus + di_minus

        dx = 100.0 * diff / denom if denom != 0 else 50.0

        # ADX SMOOTHING
        if self._update_count > 0:
            self._last_adx = ((self._period - 1) * self._last_adx + dx) / self._period

        self._last_high = high0
        self._last_low = low0
        self._last_close = close0

        # Skip: not enough values for strict warmup
        if self._update_count < self._period - 1:
            return None

        return self._last_adx

    def _build_name(self) -> str:
        result = f"ADX({self._period})"
        return result

    # endregion
