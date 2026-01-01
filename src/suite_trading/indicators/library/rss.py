from __future__ import annotations

from suite_trading.indicators.base import NumericIndicator
from suite_trading.indicators.library.ema import EMA
from suite_trading.indicators.library.rsi import RSI
from suite_trading.indicators.library.sma import SMA


class RSS(NumericIndicator):
    """Calculates the Relative Spread Strength (RSS).

    RSS is the Relative Strength Index (RSI) of the spread between two
    exponential moving averages, smoothed by a simple moving average.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, ema1_period: int = 10, ema2_period: int = 40, rsi_period: int = 5, sma_period: int = 5, max_history: int = 100):
        """Initializes RSS with periods for EMAs, RSI and smoothing.

        Args:
            ema1_period: Period for the first EMA.
            ema2_period: Period for the second EMA.
            rsi_period: Period for the RSI of the spread.
            sma_period: Smoothing period for the final result.
            max_history: Number of last calculated values stored.
        """
        # Raise: periods must be positive
        if ema1_period < 1 or ema2_period < 1 or rsi_period < 1 or sma_period < 1:
            raise ValueError("Cannot call `__init__` because all periods must be positive")

        super().__init__(max_history)

        self._ema1_period = ema1_period
        self._ema2_period = ema2_period
        self._rsi_period = rsi_period
        self._sma_period = sma_period

        self._ema1 = EMA(ema1_period)
        self._ema2 = EMA(ema2_period)
        self._rsi = RSI(rsi_period)
        self._sma = SMA(sma_period)

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        super().reset()
        self._ema1.reset()
        self._ema2.reset()
        self._rsi.reset()
        self._sma.reset()

    # endregion

    # region Properties

    @property
    def ema1_period(self) -> int:
        return self._ema1_period

    @property
    def ema2_period(self) -> int:
        return self._ema2_period

    @property
    def rsi_period(self) -> int:
        return self._rsi_period

    @property
    def sma_period(self) -> int:
        return self._sma_period

    # endregion

    # region Utilities

    def _calculate(self, value: float) -> float | None:
        """Computes the latest RSS value."""
        # UPDATE EMAs
        self._ema1.update(value)
        self._ema2.update(value)

        ema1_val = self._ema1.value
        ema2_val = self._ema2.value

        # Skip: wait for EMAs to warm up
        if ema1_val is None or ema2_val is None:
            return None

        # CALCULATE SPREAD AND UPDATE RSI
        spread = ema1_val - ema2_val
        self._rsi.update(spread)

        rsi_val = self._rsi.value

        # Skip: wait for RSI to warm up
        if rsi_val is None:
            return None

        # UPDATE SMA AND GET FINAL VALUE
        self._sma.update(rsi_val)
        result = self._sma.value

        return result

    def _build_name(self) -> str:
        result = f"RSS({self._ema1_period}, {self._ema2_period}, {self._rsi_period})"
        return result

    # endregion
