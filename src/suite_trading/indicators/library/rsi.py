from __future__ import annotations

from suite_trading.indicators.base import BaseIndicator


class RSI(BaseIndicator):
    """Calculates the Relative Strength Index (RSI).

    RSI is a momentum oscillator that measures the speed and change of price movements.
    This implementation uses Wilder's smoothing method (similar to an EMA).
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period: int = 14, max_history: int = 100):
        """Initializes RSI with a specific lookback period.

        Args:
            period: Lookback period for the average gains and losses.
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot create `RSI` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        self._last_price: float | None = None
        self._avg_gain: float = 0.0
        self._avg_loss: float = 0.0

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        super().reset()
        self._last_price = None
        self._avg_gain = 0.0
        self._avg_loss = 0.0

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    # endregion

    # region Utilities

    def _calculate(self, value: float) -> float | None:
        """Computes the latest RSI value using Wilder's smoothing."""
        # INITIALIZATION (Store the first price to compute change on the next update)
        if self._last_price is None:
            self._last_price = value
            return None

        # COMPUTE GAIN/LOSS
        change = value - self._last_price
        self._last_price = value

        gain = max(0.0, change)
        loss = max(0.0, -change)

        # WARMUP (First $period changes)
        # Note: We need $period + 1 prices to have $period changes.
        if self._update_count < self._period:
            # We use the arithmetic mean (SMA) for the initial averages
            self._avg_gain += gain / self._period
            self._avg_loss += loss / self._period

            # Skip: not enough values for initial SMA
            if self._update_count < self._period - 1:
                return None
        else:
            # WILDER'S SMOOTHING (Recursive EMA-like formula)
            # Formula: AvgGain = (PrevAvgGain * (period - 1) + current_gain) / period
            self._avg_gain = (self._avg_gain * (self._period - 1) + gain) / self._period
            self._avg_loss = (self._avg_loss * (self._period - 1) + loss) / self._period

        # RSI CALCULATION
        # Return 100 if there were no losses to avoid division by zero
        if self._avg_loss == 0:
            return 100.0

        rs = self._avg_gain / self._avg_loss
        result = 100.0 - (100.0 / (1.0 + rs))

        return result

    def _build_name(self) -> str:
        result = f"RSI({self._period})"
        return result

    # endregion
