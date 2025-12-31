from __future__ import annotations

from collections import deque

from suite_trading.indicators.base import BaseIndicator


class SimpleMovingAverage(BaseIndicator):
    """Calculates the arithmetic mean of the last $period values.

    This implementation uses a running sum to maintain O(1) performance
    regardless of the lookback period. Calculations use float primitives
    for maximum speed during backtesting.
    """

    # region Init

    def __init__(self, period: int, max_history: int = 100):
        """Initializes the SMA with a specific lookback period.

        Args:
            period: Lookback period for the average calculation.
            max_history: Number of last calculated values stored
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `SimpleMovingAverage` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        self._sum = 0.0
        self._prices: deque[float] = deque(maxlen=period)

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset

        Resets the sum and price history.
        """
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
        """Computes the latest average using a running sum."""
        # Remove oldest value from sum if the window is full
        if len(self._prices) == self._period:
            self._sum -= self._prices[0]

        # Update sum and price history
        self._sum += value
        self._prices.append(value)

        # Skip: not enough values for the average
        if len(self._prices) < self._period:
            return None

        # Compute the simple moving average
        result = self._sum / self._period
        return result

    def _build_name(self) -> str:
        result = f"SMA({self._period})"
        return result

    # endregion
