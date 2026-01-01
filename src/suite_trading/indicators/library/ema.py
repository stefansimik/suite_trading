from __future__ import annotations

from suite_trading.indicators.base import NumericIndicator


class EMA(NumericIndicator):
    """Calculates the Exponential Moving Average (EMA).

    The EMA applies more weight to recent prices than the SMA.
    This implementation uses a smoothing constant based on the period.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, period: int, max_history: int = 100):
        """Initializes the EMA with a specific lookback period.

        Args:
            period: Lookback period for the average calculation.
            max_history: Number of last calculated values stored.
        """
        # Raise: period must be positive
        if period < 1:
            raise ValueError(f"Cannot call `__init__` because $period ({period}) < 1")

        super().__init__(max_history)

        self._period = period
        self._alpha = 2.0 / (period + 1.0)
        self._last_ema: float | None = None

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        super().reset()
        self._last_ema = None

    # endregion

    # region Properties

    @property
    def period(self) -> int:
        return self._period

    # endregion

    # region Utilities

    def _calculate(self, value: float) -> float | None:
        """Computes the latest EMA value using a recursive formula."""
        # UPDATE EMA STATE
        if self._last_ema is None:
            # First value is used as the starting point
            self._last_ema = value
        else:
            # Formula: EMA = Price * alpha + PrevEMA * (1 - alpha)
            self._last_ema = (value * self._alpha) + (self._last_ema * (1.0 - self._alpha))

        # Skip: not enough values for strict warmup
        # We return None until we have seen $period updates.
        if self._update_count < self._period - 1:
            return None

        return self._last_ema

    def _build_name(self) -> str:
        result = f"EMA({self._period})"
        return result

    # endregion
