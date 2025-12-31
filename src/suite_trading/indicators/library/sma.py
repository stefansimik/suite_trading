from __future__ import annotations

from collections import deque
from decimal import Decimal

from suite_trading.indicators.base import BaseIndicator


class SimpleMovingAverage(BaseIndicator):
    """Calculates the arithmetic mean of the last $period values."""

    # region Init

    def __init__(self, period: int, max_values_to_keep: int = 100):
        """Initializes the SMA with a specific lookback period."""
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `SimpleMovingAverage` because $period ({period}) < 1")

        super().__init__(max_values_to_keep)

        self._period = period
        self._prices: deque[Decimal] = deque(maxlen=period)

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        super().reset()
        self._prices.clear()

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    # endregion

    # region Utilities

    def _calculate(self, value: Decimal) -> Decimal | None:
        """Computes the latest average using a sliding window of values."""
        self._prices.append(value)

        # Skip: not enough values for the average
        if len(self._prices) < self._period:
            return None

        result = sum(self._prices) / self._period
        return result

    def _build_name(self) -> str:
        result = f"SMA({self._period})"
        return result

    # endregion
