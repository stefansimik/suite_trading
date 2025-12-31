from __future__ import annotations

from collections import deque
from decimal import Decimal
from typing import NamedTuple

from suite_trading.indicators.base import BaseIndicator


# Justification: Group related band values for cleaner access and attribute naming
class BollingerBandsValues(NamedTuple):
    """Container for Bollinger Bands output components."""

    upper: Decimal
    middle: Decimal
    lower: Decimal


class BollingerBands(BaseIndicator):
    """Calculates Bollinger Bands (Upper, Middle, Lower)."""

    # region Init

    def __init__(self, period: int = 20, std_dev: float = 2.0, max_values_to_keep: int = 100):
        """Initializes Bollinger Bands with period and standard deviation."""
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `BollingerBands` because $period ({period}) < 1")

        super().__init__(max_values_to_keep)

        self._period = period
        self._std_dev_multiplier = Decimal(str(std_dev))
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

    @property
    def upper(self) -> Decimal | None:
        result = self.value.upper if self.value else None
        return result

    @property
    def middle(self) -> Decimal | None:
        result = self.value.middle if self.value else None
        return result

    @property
    def lower(self) -> Decimal | None:
        result = self.value.lower if self.value else None
        return result

    # endregion

    # region Utilities

    def _calculate(self, value: Decimal) -> BollingerBandsValues | None:
        """Computes bands based on a sliding window of values."""
        self._prices.append(value)

        # Skip: not enough values for the calculation
        if len(self._prices) < self._period:
            return None

        # Calculate Middle Band (SMA)
        middle = sum(self._prices) / self._period

        # Calculate Population Standard Deviation
        variance = sum((p - middle) ** 2 for p in self._prices) / self._period
        std_dev = variance.sqrt()

        # Calculate Bands
        upper = middle + (std_dev * self._std_dev_multiplier)
        lower = middle - (std_dev * self._std_dev_multiplier)

        result = BollingerBandsValues(upper=upper, middle=middle, lower=lower)
        return result

    def _build_name(self) -> str:
        result = f"BB({self._period}, {self._std_dev_multiplier})"
        return result

    # endregion
