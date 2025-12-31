from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.utils.datetime_tools import format_range, expect_utc
from suite_trading.utils.numeric_tools import DecimalLike, as_decimal


class Bar:
    """Represents a time period in financial markets with OHLC price data and optional volume.

    Time Interval Convention:
        Bars use LEFT-CLOSED, RIGHT-CLOSED intervals [start_dt, end_dt], meaning both the start
        and end timestamps are included in the bar period. For example, a 5-minute bar ending
        at 15:35:00 covers the period [15:30:00, 15:35:00], including both boundary timestamps.

        For detailed explanation of why this convention is used, see: docs/bar-time-intervals.md

    Attributes:
        bar_type (BarType): Contains instrument, period, and price type information.
        start_dt (datetime): The datetime representing the start of the bar period (timezone-aware).
        end_dt (datetime): The datetime representing the end of the bar period (timezone-aware).
        open (Decimal): The opening price for the period.
        high (Decimal): The highest price reached during the period.
        low (Decimal): The lowest price reached during the period.
        close (Decimal): The closing price for the period.
        volume (Optional[Decimal]): The trading volume during the period (optional).
        instrument (Instrument): The financial instrument identifier (delegated from $bar_type).
        value (int): The numeric value of the period (delegated from $bar_type).
        unit (BarUnit): The unit of the period (delegated from $bar_type).
        price_type (PriceType): Delegated from $bar_type. See `BarType.price_type` for
            the semantics of the underlying series used to construct this bar.
        is_partial (bool): Whether the bar was aggregated from incomplete input data.
            This is metadata only and does not affect equality of Bar instances.
    """

    __slots__ = (
        "_bar_type",
        "_start_dt",
        "_end_dt",
        "_open",
        "_high",
        "_low",
        "_close",
        "_volume",
        "_is_partial",
    )

    def __init__(
        self,
        bar_type: BarType,
        start_dt: datetime,
        end_dt: datetime,
        open: DecimalLike,
        high: DecimalLike,
        low: DecimalLike,
        close: DecimalLike,
        volume: DecimalLike,
        *,
        is_partial: bool = False,
    ):
        """Initialize a new bar.

        Args:
            bar_type: Contains instrument, period, and price type information.
            start_dt: The datetime representing the start of the bar period (timezone-aware).
            end_dt: The datetime representing the end of the bar period (timezone-aware).
            open: The opening price for the period.
            high: The highest price reached during the period.
            low: The lowest price reached during the period.
            close: The closing price for the period.
            volume: The trading volume during the period (optional).
            is_partial: Whether this bar was aggregated from incomplete input data. Defaults to False.
                Note: `is_partial` is an informational hint and does not participate in `Bar` equality.

        Raises:
            ValueError: If datetime values are not timezone-aware, end_dt is not after start_dt,
                       or OHLC price relationships are invalid.
        """
        # Store bar_type and datetime values
        self._bar_type = bar_type
        self._start_dt = expect_utc(start_dt)
        self._end_dt = expect_utc(end_dt)

        # Explicit type conversion for prices
        self._open = as_decimal(open)
        self._high = as_decimal(high)
        self._low = as_decimal(low)
        self._close = as_decimal(close)
        self._volume = as_decimal(volume) if volume is not None else None
        self._is_partial = bool(is_partial)

        # Ensure end_dt is after start_dt
        if self._end_dt <= self._start_dt:
            raise ValueError(f"$end_dt ({self._end_dt}) must be after $start_dt ({self._start_dt})")

        # Validate high price
        if self._high < self._open or self._high < self._low or self._high < self._close:
            raise ValueError(f"$high price ({self._high}) must be greater than or equal to all other prices: open={self._open}, low={self._low}, close={self._close}")

        # Validate low price
        if self._low > self._open or self._low > self._high or self._low > self._close:
            raise ValueError(f"$low price ({self._low}) must be less than or equal to all other prices: open={self._open}, high={self._high}, close={self._close}")

    @property
    def bar_type(self) -> BarType:
        """Get the bar type."""
        return self._bar_type

    @property
    def start_dt(self) -> datetime:
        """Get the start datetime."""
        return self._start_dt

    @property
    def end_dt(self) -> datetime:
        """Get the end datetime."""
        return self._end_dt

    @property
    def open(self) -> Decimal:
        """Get the opening price."""
        return self._open

    @property
    def high(self) -> Decimal:
        """Get the high price."""
        return self._high

    @property
    def low(self) -> Decimal:
        """Get the low price."""
        return self._low

    @property
    def close(self) -> Decimal:
        """Get the closing price."""
        return self._close

    @property
    def volume(self) -> Decimal | None:
        """Get the volume."""
        return self._volume

    @property
    def is_partial(self) -> bool:
        """Return whether this bar was aggregated from incomplete input data."""
        return self._is_partial

    @property
    def instrument(self) -> Instrument:
        """Get the instrument from bar_type."""
        return self.bar_type.instrument

    @property
    def value(self) -> int:
        """Get the value from bar_type."""
        return self.bar_type.value

    @property
    def unit(self) -> BarUnit:
        """Get the unit from bar_type."""
        return self.bar_type.unit

    @property
    def price_type(self) -> PriceType:
        """Return the delegated $price_type from $bar_type.

        See `BarType.price_type` for the meaning of this field.
        """
        return self.bar_type.price_type

    def __str__(self) -> str:
        """Return a string representation of the bar.

        Returns:
            str: A human-readable string representation.
        """
        volume_str = f", volume={self.volume}" if self.volume is not None else ""
        partial_str = ", partial" if self.is_partial else ""
        dt_str = format_range(self.start_dt, self.end_dt)
        return f"{self.__class__.__name__}({self.bar_type}, {dt_str}, OHLC={self.open}/{self.high}/{self.low}/{self.close}{volume_str}{partial_str})"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the bar.

        Returns:
            str: A detailed string representation.
        """
        # Use consistent datetime formatting in developer representation
        _dt = format_range(self.start_dt, self.end_dt)
        return f"{self.__class__.__name__}(bar_type={self.bar_type!r}, dt={_dt}, open={self.open}, high={self.high}, low={self.low}, close={self.close}, volume={self.volume}, is_partial={self.is_partial})"

    def __eq__(self, other) -> bool:
        """Check equality with another bar.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if bar are equal, False otherwise.
        """
        if not isinstance(other, Bar):
            return False
        return self.bar_type == other.bar_type and self.start_dt == other.start_dt and self.end_dt == other.end_dt and self.open == other.open and self.high == other.high and self.low == other.low and self.close == other.close and self.volume == other.volume
