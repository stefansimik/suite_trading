from __future__ import annotations

from typing import Any, NamedTuple

from suite_trading.indicators.base import BaseIndicator
from suite_trading.indicators.library.minimum import Minimum
from suite_trading.indicators.library.maximum import Maximum
from suite_trading.indicators.library.sma import SimpleMovingAverage


class StochasticsValues(NamedTuple):
    """Container for Stochastics output components."""

    k: float
    d: float


class Stochastics(BaseIndicator):
    """Calculates the Stochastic Oscillator (%K and %D).

    The Stochastic Oscillator measures the position of the price relative
    to its range over a set number of periods.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period_k: int = 14, period_d: int = 7, smooth: int = 3, max_history: int = 100):
        """Initializes Stochastics with periods for K, D and smoothing.

        Args:
            period_k: Lookback period for finding the high/low range.
            period_d: Lookback period for the %D average.
            smooth: Smoothing period for the %K line.
            max_history: Number of last calculated values stored.
        """
        # Raise: periods must be positive
        if period_k < 1 or period_d < 1 or smooth < 1:
            raise ValueError(f"Cannot create `Stochastics` because periods must be positive. Got period_k={period_k}, period_d={period_d}, smooth={smooth}")

        super().__init__(max_history)

        self._period_k = period_k
        self._period_d = period_d
        self._smooth = smooth

        self._min = Minimum(period_k)
        self._max = Maximum(period_k)
        self._sma_fast_k = SimpleMovingAverage(smooth)
        self._sma_k = SimpleMovingAverage(period_d)

        self._last_fast_k = 50.0

    # endregion

    # region Protocol Indicator

    def update(self, value: Any) -> None:
        """Updates the indicator.

        Note: Stochastics requires OHLC data. It is recommended to pass a `Bar` object.
        """
        # Check if the object looks like a Bar (has high, low, close)
        if not (hasattr(value, "high") and hasattr(value, "low") and hasattr(value, "close")):
            return

        high = float(value.high)
        low = float(value.low)
        close = float(value.close)

        # UPDATE MIN/MAX
        self._min.update(low)
        self._max.update(high)

        min_val = self._min.value
        max_val = self._max.value

        if min_val is not None and max_val is not None:
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

            if k is not None:
                self._sma_k.update(k)
                d = self._sma_k.value

                if d is not None:
                    result = StochasticsValues(k=k, d=d)
                    self._values.appendleft(result)

        self._update_count += 1

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

    def _calculate(self, value: float) -> Any:
        """Not used as `update` is overridden for Bar support."""
        return None

    def _build_name(self) -> str:
        result = f"Stochastics({self._period_k}, {self._period_d}, {self._smooth})"
        return result

    def _compute_warmup_period(self) -> int:
        # Justification: Stochastics needs all internal indicators to warm up
        result = self._period_k + self._smooth + self._period_d - 2
        return result

    # endregion
