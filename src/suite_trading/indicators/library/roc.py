from __future__ import annotations

from collections import deque

from suite_trading.indicators.base import NumericIndicator


class ROC(NumericIndicator):
    """Calculates the Rate of Change (ROC) indicator.

    ROC is the percentage change between the current price and the price $period bars ago.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period: int, max_history: int = 100):
        """Initializes ROC with a specific lookback period.

        Args:
            period: Lookback period for the change calculation.
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot call `__init__` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        # We need $period + 1 prices to calculate the difference with the price $period bars ago.
        self._prices: deque[float] = deque(maxlen=period + 1)

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

    def _calculate(self, value: float) -> float | None:
        """Computes the latest ROC value."""
        self._prices.append(value)

        # Skip: not enough values for the lookback period
        if len(self._prices) < self._period + 1:
            return None

        prev_price = self._prices[0]

        # Handle division by zero
        if prev_price == 0:
            return 0.0

        # ROC = ((current_price - price_n_bars_ago) / price_n_bars_ago) * 100
        result = ((value - prev_price) / prev_price) * 100.0
        return result

    def _build_name(self) -> str:
        result = f"ROC({self._period})"
        return result

    # endregion
