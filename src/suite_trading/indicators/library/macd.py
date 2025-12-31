from __future__ import annotations

from typing import NamedTuple

from suite_trading.indicators.base import BaseIndicator


class MACDValues(NamedTuple):
    """Container for MACD output components."""

    macd: float
    signal: float
    histogram: float


class MACD(BaseIndicator):
    """Calculates Moving Average Convergence/Divergence (MACD).

    MACD is calculated as the difference between a fast and a slow EMA.
    A signal line (EMA of the MACD) and a histogram (difference between
    MACD and signal line) are also provided.
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, max_history: int = 100):
        """Initializes MACD with fast, slow, and signal periods.

        Args:
            fast_period: Lookback period for the fast EMA.
            slow_period: Lookback period for the slow EMA.
            signal_period: Lookback period for the signal line EMA.
            max_history: Number of last calculated values stored.
        """
        # Raise: periods must be positive
        if fast_period < 1 or slow_period < 1 or signal_period < 1:
            raise ValueError(f"Cannot create `MACD` because periods must be positive. Got fast={fast_period}, slow={slow_period}, signal={signal_period}")

        # Raise: slow period must be greater than fast period
        if slow_period <= fast_period:
            raise ValueError(f"Cannot create `MACD` because $slow_period ({slow_period}) must be greater than $fast_period ({fast_period})")

        super().__init__(max_history)

        self._fast_period = fast_period
        self._slow_period = slow_period
        self._signal_period = signal_period

        self._fast_alpha = 2.0 / (fast_period + 1.0)
        self._slow_alpha = 2.0 / (slow_period + 1.0)
        self._signal_alpha = 2.0 / (signal_period + 1.0)

        self._fast_ema: float | None = None
        self._slow_ema: float | None = None
        self._signal_ema: float | None = None

    # endregion

    # region Protocol Indicator

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        super().reset()
        self._fast_ema = None
        self._slow_ema = None
        self._signal_ema = None

    # endregion

    # region Properties

    @property
    def fast_period(self) -> int:
        return self._fast_period

    @property
    def slow_period(self) -> int:
        return self._slow_period

    @property
    def signal_period(self) -> int:
        return self._signal_period

    @property
    def macd(self) -> float | None:
        result = self.value.macd if self.value else None
        return result

    @property
    def signal(self) -> float | None:
        result = self.value.signal if self.value else None
        return result

    @property
    def histogram(self) -> float | None:
        result = self.value.histogram if self.value else None
        return result

    # endregion

    # region Utilities

    def _calculate(self, value: float) -> MACDValues | None:
        """Computes the latest MACD values."""
        # UPDATE FAST EMA
        if self._fast_ema is None:
            self._fast_ema = value
        else:
            self._fast_ema = (value * self._fast_alpha) + (self._fast_ema * (1.0 - self._fast_alpha))

        # UPDATE SLOW EMA
        if self._slow_ema is None:
            self._slow_ema = value
        else:
            self._slow_ema = (value * self._slow_alpha) + (self._slow_ema * (1.0 - self._slow_alpha))

        macd = self._fast_ema - self._slow_ema

        # UPDATE SIGNAL EMA (EMA of the MACD)
        if self._signal_ema is None:
            self._signal_ema = macd
        else:
            self._signal_ema = (macd * self._signal_alpha) + (self._signal_ema * (1.0 - self._signal_alpha))

        histogram = macd - self._signal_ema

        # Skip: not enough values for strict warmup
        # MACD needs both EMAs to warm up, and then the signal line needs its period.
        if self._update_count < (self._slow_period + self._signal_period - 2):
            return None

        result = MACDValues(macd=macd, signal=self._signal_ema, histogram=histogram)
        return result

    def _build_name(self) -> str:
        result = f"MACD({self._fast_period}, {self._slow_period}, {self._signal_period})"
        return result

    def _compute_warmup_period(self) -> int:
        # Justification: MACD needs slow period + signal period to stabilize
        result = self._slow_period + self._signal_period - 1
        return result

    # endregion
