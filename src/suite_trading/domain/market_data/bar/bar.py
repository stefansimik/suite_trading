from datetime import datetime
from decimal import Decimal
from typing import Optional, Union

from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.price_type import PriceType


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
        instrument (Instrument): The financial instrument identifier (delegated from bar_type).
        value (int): The numeric value of the period (delegated from bar_type).
        unit (BarUnit): The unit of the period (delegated from bar_type).
        price_type (PriceType): The type of price data (delegated from bar_type).
    """

    def __init__(
        self,
        bar_type: BarType,
        start_dt: datetime,
        end_dt: datetime,
        open: Union[Decimal, str, float],
        high: Union[Decimal, str, float],
        low: Union[Decimal, str, float],
        close: Union[Decimal, str, float],
        volume: Optional[Union[Decimal, str, float]] = None,
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

        Raises:
            ValueError: If datetime values are not timezone-aware, end_dt is not after start_dt,
                       or OHLC price relationships are invalid.
        """
        # Store bar_type and datetime values
        self._bar_type = bar_type
        self._start_dt = start_dt
        self._end_dt = end_dt

        # Explicit type conversion for prices
        self._open = Decimal(str(open))
        self._high = Decimal(str(high))
        self._low = Decimal(str(low))
        self._close = Decimal(str(close))
        self._volume = Decimal(str(volume)) if volume is not None else None

        # Explicit validation
        # Ensure datetimes are timezone-aware
        if self._start_dt.tzinfo is None:
            raise ValueError(f"$start_dt must be timezone-aware, but provided value is: {self._start_dt}")
        if self._end_dt.tzinfo is None:
            raise ValueError(f"$end_dt must be timezone-aware, but provided value is: {self._end_dt}")

        # Ensure end_dt is after start_dt
        if self._end_dt <= self._start_dt:
            raise ValueError(f"$end_dt ({self._end_dt}) must be after $start_dt ({self._start_dt})")

        # Validate high price
        if self._high < self._open or self._high < self._low or self._high < self._close:
            raise ValueError(
                f"$high price ({self._high}) must be greater than or equal to all other prices: open={self._open}, low={self._low}, close={self._close}",
            )

        # Validate low price
        if self._low > self._open or self._low > self._high or self._low > self._close:
            raise ValueError(
                f"$low price ({self._low}) must be less than or equal to all other prices: open={self._open}, high={self._high}, close={self._close}",
            )

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
    def volume(self) -> Optional[Decimal]:
        """Get the volume."""
        return self._volume

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
        """Get the price_type from bar_type."""
        return self.bar_type.price_type

    def __str__(self) -> str:
        """Return a string representation of the bar.

        Returns:
            str: A human-readable string representation.
        """
        volume_str = f", volume={self.volume}" if self.volume is not None else ""
        return f"{self.__class__.__name__}({self.bar_type}, {self.start_dt}-{self.end_dt}, OHLC={self.open}/{self.high}/{self.low}/{self.close}{volume_str})"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the bar.

        Returns:
            str: A detailed string representation.
        """
        return (
            f"{self.__class__.__name__}(bar_type={self.bar_type!r}, start_dt={self.start_dt!r}, end_dt={self.end_dt!r}, "
            f"open={self.open}, high={self.high}, low={self.low}, close={self.close}, volume={self.volume})"
        )

    def __eq__(self, other) -> bool:
        """Check equality with another bar.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if bars are equal, False otherwise.
        """
        if not isinstance(other, Bar):
            return False
        return (
            self.bar_type == other.bar_type
            and self.start_dt == other.start_dt
            and self.end_dt == other.end_dt
            and self.open == other.open
            and self.high == other.high
            and self.low == other.low
            and self.close == other.close
            and self.volume == other.volume
        )
