from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType


class BarAccumulator:
    """Accumulate OHLCV across Bar(s).

    Purpose:
        Reusable Bar-only accumulator independent of event system and windowing.

    Notes:
        - Enforces consistent BarType across all added bars in a window.
        - Treats None volume as Decimal("0").
    """

    # region Init

    def __init__(self) -> None:
        self._open: Optional[Decimal] = None
        self._high: Optional[Decimal] = None
        self._low: Optional[Decimal] = None
        self._close: Optional[Decimal] = None
        self._volume: Decimal = Decimal("0")
        self._first_bar_type: Optional[BarType] = None
        self._count: int = 0

    # endregion

    # region Main

    def reset(self) -> None:
        """Clear accumulated state for a new window."""
        self._first_bar_type = None
        self._count = 0
        self._open = None
        self._high = None
        self._low = None
        self._close = None
        self._volume = Decimal("0")

    def has_data(self) -> bool:
        """Return True if at least one bar has been added."""
        return self._count > 0

    def add(self, bar: Bar) -> None:
        """Add a Bar and update OHLCV state.

        Args:
            bar (Bar): Input bar to accumulate.

        Raises:
            ValueError: If $bar is not Bar or BarType mismatch vs first bar type.
        """
        # Check: ensure $bar is a Bar instance to maintain type safety
        if not isinstance(bar, Bar):
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add` because $bar (class '{type(bar).__name__}') is not a Bar")

        # Enforce consistent BarType across the window
        if self._first_bar_type is None:
            self._first_bar_type = bar.bar_type
        elif self._first_bar_type != bar.bar_type:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add` because $bar.bar_type ('{bar.bar_type}') differs from the first bar type ('{self._first_bar_type}')")

        # Initialize on first element
        if self._count == 0:
            self._open = bar.open
            self._high = bar.high
            self._low = bar.low
            self._close = bar.close
            self._volume += bar.volume if bar.volume is not None else Decimal("0")
        else:
            # Update OHLCV (Open fixed from first)
            if bar.high > (self._high if self._high is not None else bar.high):
                self._high = bar.high
            if bar.low < (self._low if self._low is not None else bar.low):
                self._low = bar.low
            self._close = bar.close
            self._volume += bar.volume if bar.volume is not None else Decimal("0")

        self._count += 1

    # endregion

    # region Build outputs
    def build_bar(
        self,
        out_bar_type: BarType,
        start_dt: datetime | None,
        end_dt: datetime | None,
        *,
        is_partial: bool,
    ) -> Bar:
        """Create an aggregated Bar from the current accumulation state.

        Args:
            out_bar_type (BarType): Target BarType for the aggregated bar.
            start_dt (datetime): Output bar start time (UTC).
            end_dt (datetime): Output bar end time (UTC).
            is_partial (bool): Whether the window is partial.

        Returns:
            Bar: Aggregated bar reflecting OHLCV and flags.

        Raises:
            ValueError: If $start_dt or $end_dt is None.
        """
        # Check: require $start_dt and $end_dt to define the output interval
        if start_dt is None or end_dt is None:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.build_bar` because $start_dt or $end_dt is None")

        return Bar(
            bar_type=out_bar_type,
            start_dt=start_dt,
            end_dt=end_dt,
            open=self._open,
            high=self._high,
            low=self._low,
            close=self._close,
            volume=self._volume,
            is_partial=is_partial,
        )

    # endregion

    # region Magic methods

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(count={self._count}, volume={self._volume})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(count={self._count!r}, volume={self._volume!r})"

    # endregion

    # region Access properties

    @property
    def first_bar_type(self) -> Optional[BarType]:
        return self._first_bar_type

    @property
    def count(self) -> int:
        return self._count

    # endregion
