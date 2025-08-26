from __future__ import annotations  # enables lazy evaluation of annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType


class OhlcvAccumulator:
    """Accumulate open, high, low, close, and volume (OHLCV) from many Bars into one Bar.

    This class does not manage time windows. You add Bars to it, then build one Bar by passing
    the target $bar_type, $start_dt, and $end_dt.
    """

    # region Init

    def __init__(self) -> None:
        # First BarType in the window
        self.first_bar_type: Optional[BarType] = None

        # OHLCV values
        self.open: Optional[Decimal] = None
        self.high: Optional[Decimal] = None
        self.low: Optional[Decimal] = None
        self.close: Optional[Decimal] = None
        self.volume: Decimal = Decimal("0")

    # endregion

    # region Main

    def reset(self) -> None:
        """Clear accumulated state for a new window."""
        # Clean first BarType
        self.first_bar_type = None

        # Clean OHLCV values
        self.open = None
        self.high = None
        self.low = None
        self.close = None
        self.volume = Decimal("0")

    def add(self, bar: Bar) -> None:
        """Add $bar and update open/high/low/close and sum volume.

        Args:
            bar (Bar): Source Bar.

        Raises:
            ValueError: If $bar.bar_type is different from the first BarType in this window.
        """
        adding_first_bar = self.open is None
        if adding_first_bar:
            # Set first BarType
            self.first_bar_type = bar.bar_type

            # Set initial OHLCV value
            self.open = bar.open
            self.high = bar.high
            self.low = bar.low
            self.close = bar.close
            self.volume += bar.volume
        else:
            # Check: last added bar-type is the same as first bar-type
            self._require_same_bartype(bar.bar_type)
            # Accumulate HLCV (Open price is fixed already)
            self.high = bar.high if bar.high > self.high else self.high
            self.low = bar.low if bar.low < self.low else self.low
            self.close = bar.close
            self.volume += bar.volume

    def get_aggregated_bar(self, bar_type: BarType, start_dt: datetime, end_dt: datetime) -> Bar:
        """Build one Bar for [$start_dt, $end_dt] using the accumulated OHLCV.

        Args:
            bar_type (BarType): BarType of the result.
            start_dt (datetime): Start of the window.
            end_dt (datetime): End of the window.

        Returns:
            Bar: A Bar with open/high/low/close and volume from the current window.
        """
        return Bar(
            bar_type=bar_type,
            start_dt=start_dt,
            end_dt=end_dt,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )

    # endregion

    # region Empty or not

    def is_empty(self) -> bool:
        """Return True if no Bars were added in the current window."""
        return self.open is None

    def has_data(self) -> bool:
        """Return True if at least one Bar was added in the current window."""
        return not self.is_empty()

    # endregion

    # region Internal

    def _require_same_bartype(self, bar_type):
        """Require $bar_type to be the same as $self.first_bar_type.

        Args:
            bar_type (BarType): Type of the next Bar being added.

        Raises:
            ValueError: If $bar_type is different from $self.first_bar_type.
        """
        if not self.first_bar_type != bar_type:
            raise ValueError(f"{self.__class__.__name__} cannot accept mixed bar-types in one window. | First bar-type: {self.first_bar_type} | Later bar-type: {bar_type}")

    # endregion
