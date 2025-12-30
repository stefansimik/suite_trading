from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import BarEvent
from suite_trading.domain.market_data.bar.bar_type import BarType


class BarAccumulator:
    """Accumulate OHLCV across Bar(s).

    Purpose:
        Reusable Bar-only accumulator independent of event system and windowing.

    Notes:
        - Enforces consistent BarType across all added bar in a window.
        - Treats None volume as Decimal("0").
    """

    # region Init

    def __init__(self) -> None:
        self._open: Decimal | None = None
        self._high: Decimal | None = None
        self._low: Decimal | None = None
        self._close: Decimal | None = None
        self._volume: Decimal = Decimal("0")
        self._first_bar_type: BarType | None = None
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
        if not isinstance(bar, Bar):
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add` because $bar (class '{type(bar).__name__}') is not a Bar")

        # Raise: all bars in an aggregation window must have the same type
        if self._first_bar_type is None:
            self._first_bar_type = bar.bar_type
        elif self._first_bar_type != bar.bar_type:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add` because $bar.bar_type ('{bar.bar_type}') differs from the first bar type ('{self._first_bar_type}')")

        if self._count == 0:
            # Initialize on first element
            self._open = bar.open
            self._high = bar.high
            self._low = bar.low
            self._close = bar.close
            self._volume += bar.volume or Decimal("0")
        else:
            # Update OHLCV (Open fixed from first)
            if bar.high > self._high:
                self._high = bar.high
            if bar.low < self._low:
                self._low = bar.low
            self._close = bar.close
            self._volume += bar.volume or Decimal("0")

        self._count += 1

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
        if start_dt is None or end_dt is None:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.build_bar` because $start_dt or $end_dt is None")

        # Raise: cannot build a bar without any data
        if not self.has_data():
            raise ValueError(f"Cannot call `{self.__class__.__name__}.build_bar` because no data has been accumulated")

        # Create and return aggregated bar
        result = Bar(out_bar_type, start_dt, end_dt, self._open, self._high, self._low, self._close, self._volume, is_partial=is_partial)
        return result

    # endregion

    # region Properties

    @property
    def first_bar_type(self) -> BarType | None:
        return self._first_bar_type

    @property
    def count(self) -> int:
        return self._count

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(count={self._count}, volume={self._volume})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(count={self._count!r}, volume={self._volume!r})"

    # endregion


class BarEventAccumulator:
    """Accumulate BarEvent(s) and emit aggregated BarEvent(s)."""

    # region Init

    def __init__(self) -> None:
        self._bar_accumulator = BarAccumulator()
        self._last_dt_received: datetime | None = None
        self._last_is_historical: bool | None = None

    # endregion

    # region Main

    def reset(self) -> None:
        """Clear accumulated state for a new window."""
        self._bar_accumulator.reset()
        self._last_dt_received = None
        self._last_is_historical = None

    def has_data(self) -> bool:
        """Return True if at least one event has been added."""
        return self._bar_accumulator.has_data()

    def add(self, event: BarEvent) -> None:
        """Add a BarEvent and update OHLCV and metadata.

        Args:
            event (BarEvent): Input event to accumulate.
        """
        if not isinstance(event, BarEvent):
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add` because $event (class '{type(event).__name__}') is not a BarEvent")

        self._bar_accumulator.add(event.bar)
        self._last_dt_received = event.dt_received
        self._last_is_historical = event.is_historical

    def build_event(
        self,
        out_bar_type: BarType,
        start_dt: datetime | None,
        end_dt: datetime | None,
        *,
        is_partial: bool,
    ) -> BarEvent:
        """Create a BarEvent using last included event metadata and aggregated Bar.

        Args:
            out_bar_type (BarType): Target BarType for the aggregated bar.
            start_dt (datetime | None): Output bar start time (UTC).
            end_dt (datetime | None): Output bar end time (UTC).
            is_partial (bool): Whether the aggregated window is partial.

        Returns:
            BarEvent: Aggregated event with propagated metadata.
        """
        bar = self._bar_accumulator.build_bar(out_bar_type, start_dt, end_dt, is_partial=is_partial)

        # Raise: cannot build event without received metadata
        if self._last_dt_received is None or self._last_is_historical is None:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.build_event` because missing metadata: $last_dt_received ('{self._last_dt_received}'), $last_is_historical ('{self._last_is_historical}')")

        return BarEvent(bar=bar, dt_received=self._last_dt_received, is_historical=self._last_is_historical)

    # endregion

    # region Properties

    @property
    def first_bar_type(self) -> BarType | None:
        return self._bar_accumulator.first_bar_type

    @property
    def count(self) -> int:
        return self._bar_accumulator.count

    @property
    def last_dt_received(self) -> datetime | None:
        return self._last_dt_received

    @property
    def last_is_historical(self) -> bool | None:
        return self._last_is_historical

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(count={self._bar_accumulator.count})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(count={self._bar_accumulator.count!r})"

    # endregion
