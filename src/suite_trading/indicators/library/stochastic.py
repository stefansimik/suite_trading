from __future__ import annotations

from typing import NamedTuple, TYPE_CHECKING

from suite_trading.indicators.base import BarIndicator
from suite_trading.indicators.library.min import MIN
from suite_trading.indicators.library.max import MAX
from suite_trading.indicators.library.sma import SMA

if TYPE_CHECKING:
    from suite_trading.domain.market_data.bar.bar import Bar


class StochasticValues(NamedTuple):
    """Container for Stochastic output components."""

    k: float
    d: float


class Stochastic(BarIndicator):
    """Calculates the Stochastic Oscillator (%K and %D).

    The Stochastic Oscillator measures the position of the price relative
    to its range over a set number of periods.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period_k: int = 14, period_d: int = 7, smooth: int = 3, max_history: int = 100):
        """Initializes Stochastic with periods for K, D and smoothing.

        Args:
            period_k: Lookback period for finding the high/low range.
            period_d: Lookback period for the %D average.
            smooth: Smoothing period for the %K line.
            max_history: Number of last calculated values stored.
        """
        # Raise: periods must be positive
        if period_k < 1 or period_d < 1 or smooth < 1:
            raise ValueError(f"Cannot create `Stochastic` because periods must be positive. Got period_k={period_k}, period_d={period_d}, smooth={smooth}")

        super().__init__(max_history)

        self._period_k = period_k
        self._period_d = period_d
        self._smooth = smooth

        self._min = MIN(period_k)
        self._max = MAX(period_k)
        self._sma_fast_k = SMA(smooth)
        self._sma_k = SMA(period_d)

        self._last_fast_k = 50.0

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        super().reset()
        self._min.reset()
        self._max.reset()
        self._sma_fast_k.reset()
        self._sma_k.reset()
        self._last_fast_k = 50.0

    # endregion

    # region Properties

    @property
    def period_k(self) -> int:
        return self._period_k

    @property
    def period_d(self) -> int:
        return self._period_d

    @property
    def smooth(self) -> int:
        return self._smooth

    @property
    def k(self) -> float | None:
        result = self.value.k if self.value else None
        return result

    @property
    def d(self) -> float | None:
        result = self.value.d if self.value else None
        return result

    # endregion

    # region Utilities

    def _calculate(self, bar: Bar) -> StochasticValues | None:
        """Computes the latest Stochastic values."""
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)

        # UPDATE MIN/MAX
        self._min.update(low)
        self._max.update(high)

        min_val = self._min.value
        max_val = self._max.value

        # Skip: not enough data for min/max
        if min_val is None or max_val is None:
            return None

        nom = close - min_val
        den = max_val - min_val

        if den == 0:
            fast_k = self._last_fast_k
        else:
            fast_k = min(100.0, max(0.0, 100.0 * nom / den))

        self._last_fast_k = fast_k

        # UPDATE SMAs
        self._sma_fast_k.update(fast_k)
        k = self._sma_fast_k.value

        # Skip: not enough data for smoothed K
        if k is None:
            return None

        self._sma_k.update(k)
        d = self._sma_k.value

        # Skip: not enough data for D
        if d is None:
            return None

        result = StochasticValues(k=k, d=d)
        return result

    def _build_name(self) -> str:
        result = f"Stochastic({self._period_k}, {self._period_d}, {self._smooth})"
        return result

    def _compute_warmup_period(self) -> int:
        # Justification: Stochastic needs all internal indicators to warm up
        result = self._period_k + self._smooth + self._period_d - 2
        return result

    # endregion
