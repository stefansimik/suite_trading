from __future__ import annotations

from collections import deque

from suite_trading.indicators.base import BaseIndicator


class Maximum(BaseIndicator):
    """Returns the maximum value over a specified period.

    This implementation maintains a sliding window of values and computes
    the maximum. For performance, it uses Python's built-in `max()` on a `deque`.
    """

    # region Init

    def __init__(self, period: int, max_history: int = 100):
        """Initializes the Maximum indicator with a specific period.

        Args:
            period: Lookback period for finding the maximum value.
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `Maximum` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        self._window: deque[float] = deque(maxlen=period)

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        super().reset()
        self._window.clear()

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    # endregion

    # region Utilities

    def _calculate(self, value: float) -> float | None:
        """Computes the latest maximum value."""
        self._window.append(value)

        # Skip: not enough values for the period
        if len(self._window) < self._period:
            return None

        # Return the maximum value in the current window
        result = max(self._window)
        return result

    def _build_name(self) -> str:
        result = f"MAX({self._period})"
        return result

    # endregion
