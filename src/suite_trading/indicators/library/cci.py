from __future__ import annotations

from collections import deque

from suite_trading.indicators.base import BaseIndicator


class CCI(BaseIndicator):
    """Calculates the Commodity Channel Index (CCI).

    CCI measures the variation of a security's price from its statistical mean.
    High values show that prices are unusually high compared to average prices,
    whereas low values indicate that prices are unusually low.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period: int = 14, max_history: int = 100):
        """Initializes CCI with a specific lookback period.

        Args:
            period: Lookback period for the mean and mean deviation.
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `CCI` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        self._prices: deque[float] = deque(maxlen=period)
        self._sum = 0.0

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        super().reset()
        self._prices.clear()
        self._sum = 0.0

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    # endregion

    # region Utilities

    def _calculate(self, value: float) -> float | None:
        """Computes the latest CCI value."""
        # ROLLING SUM UPDATES
        if len(self._prices) == self._period:
            self._sum -= self._prices[0]

        self._sum += value
        self._prices.append(value)

        # Skip: not enough values for the calculation
        if len(self._prices) < self._period:
            return None

        # CCI CALCULATION
        sma = self._sum / self._period

        # Compute Mean Deviation
        # Formula: MeanDev = sum(|Price_i - SMA|) / period
        mean_deviation = sum(abs(p - sma) for p in self._prices) / self._period

        # Avoid division by zero
        if mean_deviation == 0:
            return 0.0

        # CCI Formula: (Price - SMA) / (0.015 * MeanDeviation)
        result = (value - sma) / (0.015 * mean_deviation)
        return result

    def _build_name(self) -> str:
        result = f"CCI({self._period})"
        return result

    # endregion
