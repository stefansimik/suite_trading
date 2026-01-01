from __future__ import annotations

from typing import TYPE_CHECKING

from suite_trading.indicators.base import BarIndicator
from suite_trading.indicators.library.sma import SMA

if TYPE_CHECKING:
    from suite_trading.domain.market_data.bar.bar import Bar


class DMI(BarIndicator):
    """Calculates the Directional Movement Index (DMI).

    DMI measures the trend strength and direction. Unlike ADX which uses
    Wilder's smoothing, this implementation (matching NinjaTrader's DMI)
    uses Simple Moving Averages.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period: int = 14, max_history: int = 100):
        """Initializes DMI with a specific lookback period.

        Args:
            period: Lookback period for the SMA calculations.
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `DMI` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        self._last_high: float | None = None
        self._last_low: float | None = None
        self._last_close: float | None = None

        self._sma_tr = SMA(period)
        self._sma_dm_plus = SMA(period)
        self._sma_dm_minus = SMA(period)

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        super().reset()
        self._last_high = None
        self._last_low = None
        self._last_close = None
        self._sma_tr.reset()
        self._sma_dm_plus.reset()
        self._sma_dm_minus.reset()

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    # endregion

    # region Utilities

    def _calculate(self, bar: Bar) -> float | None:
        """Computes the latest DMI value."""
        high0 = float(bar.high)
        low0 = float(bar.low)
        close0 = float(bar.close)

        # INITIAL BAR
        if self._last_high is None:
            tr = high0 - low0
            dm_plus = 0.0
            dm_minus = 0.0
        else:
            # TRUE RANGE & DIRECTIONAL MOVEMENT
            tr = max(high0 - low0, abs(high0 - self._last_close), abs(low0 - self._last_close))

            diff_high = high0 - self._last_high
            diff_low = self._last_low - low0

            dm_plus = max(diff_high, 0.0) if diff_high > diff_low else 0.0
            dm_minus = max(diff_low, 0.0) if diff_low > diff_high else 0.0

        self._last_high = high0
        self._last_low = low0
        self._last_close = close0

        # UPDATE INTERNAL SMAs
        self._sma_tr.update(tr)
        self._sma_dm_plus.update(dm_plus)
        self._sma_dm_minus.update(dm_minus)

        # CALCULATE DMI VALUE
        sma_tr = self._sma_tr.value
        sma_dm_plus = self._sma_dm_plus.value
        sma_dm_minus = self._sma_dm_minus.value

        # Skip: not enough data for SMAs
        if sma_tr is None or sma_dm_plus is None or sma_dm_minus is None:
            return None

        di_plus = sma_dm_plus / sma_tr if sma_tr != 0 else 0.0
        di_minus = sma_dm_minus / sma_tr if sma_tr != 0 else 0.0

        denom = di_plus + di_minus
        result = (di_plus - di_minus) / denom if denom != 0 else 0.0
        return result

    def _build_name(self) -> str:
        result = f"DMI({self._period})"
        return result

    # endregion
