from __future__ import annotations

from collections import deque

from suite_trading.indicators.base import BaseIndicator


class Momentum(BaseIndicator):
    """Calculates the Momentum indicator.

    Momentum is the difference between the current price and the price $period bars ago.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period: int, max_history: int = 100):
        """Initializes Momentum with a specific lookback period.

        Args:
            period: Lookback period for the change calculation.
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `Momentum` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        # We need $period + 1 prices to calculate the difference with the price $period bars ago.
        self._prices: deque[float] = deque(maxlen=period + 1)

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        super().reset()
        self._prices.clear()

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    # endregion

    # region Utilities

    def _calculate(self, value: float) -> float | None:
        """Computes the latest Momentum value."""
        self._prices.append(value)

        # Skip: not enough values for the lookback period
        if len(self._prices) < self._period + 1:
            return None

        # Momentum = current_price - price_n_bars_ago
        result = value - self._prices[0]
        return result

    def _build_name(self) -> str:
        result = f"Momentum({self._period})"
        return result

    # endregion
