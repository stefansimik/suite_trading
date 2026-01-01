from __future__ import annotations

import math
from collections import deque
from typing import NamedTuple

from suite_trading.indicators.base import NumericIndicator


class BollingerBandsValues(NamedTuple):
    """Container for Bollinger Bands output components."""

    upper: float
    middle: float
    lower: float


class BollingerBands(NumericIndicator):
    """Calculates Bollinger Bands (Upper, Middle, Lower)."""

    # region Init

    def __init__(self, period: int = 20, std_dev: float = 2.0, max_history: int = 100):
        """Initializes Bollinger Bands with period and standard deviation.

        Args:
            period: Lookback period for the average and standard deviation.
            std_dev: Multiplier for the standard deviation to set band width.
            max_history: Number of recent results to store.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot call `__init__` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        self._std_dev_multiplier = float(std_dev)
        self._prices: deque[float] = deque(maxlen=period)
        self._sum_x = 0.0
        self._sum_x2 = 0.0

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        super().reset()
        self._prices.clear()
        self._sum_x = 0.0
        self._sum_x2 = 0.0

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    @property
    def upper(self) -> float | None:
        result = self.value.upper if self.value else None
        return result

    @property
    def middle(self) -> float | None:
        result = self.value.middle if self.value else None
        return result

    @property
    def lower(self) -> float | None:
        result = self.value.lower if self.value else None
        return result

    # endregion

    # region Utilities

    def _calculate(self, value: float) -> BollingerBandsValues | None:
        """Computes bands based on a sliding window of values."""
        # ROLLING UPDATES (SMA & VAR)
        if len(self._prices) == self._period:
            old_value = self._prices[0]
            self._sum_x -= old_value
            self._sum_x2 -= old_value * old_value

        self._sum_x += value
        self._sum_x2 += value * value
        self._prices.append(value)

        # Skip: not enough values for the calculation
        if len(self._prices) < self._period:
            return None

        # BAND COMPUTATION (SMA & STD DEV)
        # Middle band is a Simple Moving Average (SMA).
        middle = self._sum_x / self._period

        # We use the identity Var(X) = E[X^2] - E[X]^2 for O(1) performance.
        # Max is used to prevent tiny negative variance from precision drift.
        variance = max(0.0, (self._sum_x2 / self._period) - (middle * middle))
        std_dev = math.sqrt(variance)

        upper = middle + (std_dev * self._std_dev_multiplier)
        lower = middle - (std_dev * self._std_dev_multiplier)

        result = BollingerBandsValues(upper=upper, middle=middle, lower=lower)
        return result

    def _build_name(self) -> str:
        result = f"BollingerBands({self._period}, {self._std_dev_multiplier})"
        return result

    # endregion
