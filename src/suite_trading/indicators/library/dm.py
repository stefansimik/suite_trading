from __future__ import annotations

from typing import Any, NamedTuple

from suite_trading.indicators.base import BaseIndicator


class DMValues(NamedTuple):
    """Container for Directional Movement output components."""

    adx: float
    di_plus: float
    di_minus: float


class DM(BaseIndicator):
    """Calculates Directional Movement (DM).

    This indicator provides the Average Directional Index (ADX) along with
    the Plus and Minus Directional Indicators (+DI and -DI).
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period: int = 14, max_history: int = 100):
        """Initializes DM with a specific lookback period.

        Args:
            period: Lookback period for the smoothing (default is 14).
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `DM` because $period ({period}) < 1")

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

    def update(self, value: Any) -> None:
        """Updates the indicator.

        Note: DM requires OHLC data. It is recommended to pass a `Bar` object.
        """
        # Check if the object looks like a Bar (has high, low, close)
        if not (hasattr(value, "high") and hasattr(value, "low") and hasattr(value, "close")):
            return

        high0 = float(value.high)
        low0 = float(value.low)
        close0 = float(value.close)

        # INITIAL BAR
        if self._last_high is None:
            tr = high0 - low0
            dm_plus = 0.0
            dm_minus = 0.0

            self._sum_tr = tr
            self._sum_dm_plus = dm_plus
            self._sum_dm_minus = dm_minus
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

        # Calculate DI+, DI-
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

        # Store result and increment count
        if self._update_count >= self._period - 1:
            result = DMValues(adx=self._last_adx, di_plus=di_plus, di_minus=di_minus)
            self._values.appendleft(result)

        self._update_count += 1

    def reset(self) -> None:
        """Implements: Indicator.reset"""
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

    @property
    def adx(self) -> float | None:
        result = self.value.adx if self.value else None
        return result

    @property
    def di_plus(self) -> float | None:
        result = self.value.di_plus if self.value else None
        return result

    @property
    def di_minus(self) -> float | None:
        result = self.value.di_minus if self.value else None
        return result

    # endregion

    # region Utilities

    def _calculate(self, value: float) -> Any:
        """Not used as `update` is overridden for Bar support."""
        return None

    def _build_name(self) -> str:
        result = f"DM({self._period})"
        return result

    # endregion
