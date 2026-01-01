from __future__ import annotations

from typing import NamedTuple

from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.indicators.base import BarIndicator


class PivotsValues(NamedTuple):
    """Container for Pivot Points output components."""

    pp: float
    r1: float
    s1: float
    r2: float
    s2: float
    r3: float
    s3: float


class Pivots(BarIndicator):
    """Calculates Standard Pivot Points (Pivots).

    Pivot points are calculated based on the High, Low, and Close prices
    of a previous period (typically a Day, Week, or Month).
    Calculations use float primitives for maximum speed.
    """

    # region Init

    def __init__(self, max_history: int = 100):
        """Initializes Pivots.

        Args:
            max_history: Number of last calculated values stored.
        """
        super().__init__(max_history)

    # endregion

    # region Properties

    @property
    def pp(self) -> float | None:
        result = self.value.pp if self.value else None
        return result

    @property
    def r1(self) -> float | None:
        result = self.value.r1 if self.value else None
        return result

    @property
    def s1(self) -> float | None:
        result = self.value.s1 if self.value else None
        return result

    @property
    def r2(self) -> float | None:
        result = self.value.r2 if self.value else None
        return result

    @property
    def s2(self) -> float | None:
        result = self.value.s2 if self.value else None
        return result

    @property
    def r3(self) -> float | None:
        result = self.value.r3 if self.value else None
        return result

    @property
    def s3(self) -> float | None:
        result = self.value.s3 if self.value else None
        return result

    # endregion

    # region Utilities

    def _calculate(self, bar: Bar) -> PivotsValues:
        """Computes the latest Pivot Points."""
        high = float(bar.high)
        low = float(bar.low)
        close = float(bar.close)

        # CORE PIVOT CALCULATION (Standard Method)
        pp = (high + low + close) / 3.0
        r1 = (2.0 * pp) - low
        s1 = (2.0 * pp) - high
        r2 = pp + (high - low)
        s2 = pp - (high - low)
        r3 = high + (2.0 * (pp - low))
        s3 = low - (2.0 * (high - pp))

        result = PivotsValues(pp=pp, r1=r1, s1=s1, r2=r2, s2=s2, r3=r3, s3=s3)
        return result

    def _build_name(self) -> str:
        return "Pivots"

    # endregion
