from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.price_type import PriceType


@dataclass(frozen=True)
class Bar:
    """Represents a time period in financial markets with OHLC price data and optional volume.

    Attributes:
        bar_type (BarType): Contains instrument, period, and price type information.
        start_dt (datetime): The datetime representing the start of the bar period (timezone-aware).
        end_dt (datetime): The datetime representing the end of the bar period (timezone-aware).
        open (Any numerical type, Decimal, or str): The opening price for the period. Any numerical type, Decimal, or string can be provided
            and will be automatically converted to Decimal internally. Strings are recommended for precise decimal representation.
        high (Any numerical type, Decimal, or str): The highest price reached during the period. Any numerical type, Decimal, or string can be provided
            and will be automatically converted to Decimal internally. Strings are recommended for precise decimal representation.
        low (Any numerical type, Decimal, or str): The lowest price reached during the period. Any numerical type, Decimal, or string can be provided
            and will be automatically converted to Decimal internally. Strings are recommended for precise decimal representation.
        close (Any numerical type, Decimal, or str): The closing price for the period. Any numerical type, Decimal, or string can be provided
            and will be automatically converted to Decimal internally. Strings are recommended for precise decimal representation.
        volume (Optional[Any numerical type, Decimal, or str]): The trading volume during the period (optional). Any numerical type, Decimal, or string can be provided
            and will be automatically converted to Decimal internally. Strings are recommended for precise decimal representation.
        instrument (Instrument): The financial instrument identifier (delegated from bar_type).
        value (int): The numeric value of the period (delegated from bar_type).
        unit (BarUnit): The unit of the period (delegated from bar_type).
        price_type (PriceType): The type of price data (delegated from bar_type).
    """

    bar_type: BarType

    start_dt: datetime
    end_dt: datetime

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    volume: Optional[Decimal] = None

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

    def __post_init__(self) -> None:
        """
        Validate the bar data after initialization.

        Raises:
            ValueError: if some data are invalid.
        """
        # Convert values to Decimal if they're not already
        for field in ["open", "high", "low", "close"]:
            value = getattr(self, field)
            if not isinstance(value, Decimal):
                # set a new converted value (bypass mechanism of frozen dataclass, that does not allow setting new value)
                object.__setattr__(self, field, Decimal(str(value)))

        # Convert volume to Decimal if it's not None and not already a Decimal
        if self.volume is not None and not isinstance(self.volume, Decimal):
            object.__setattr__(self, "volume", Decimal(str(self.volume)))

        # Ensure datetimes are timezone-aware
        if self.start_dt.tzinfo is None:
            raise ValueError(f"$start_dt must be timezone-aware, but provided value is: {self.start_dt}")
        if self.end_dt.tzinfo is None:
            raise ValueError(f"$end_dt must be timezone-aware, but provided value is: {self.end_dt}")

        # Ensure end_dt is after start_dt
        if self.end_dt <= self.start_dt:
            raise ValueError(f"$end_dt ({self.end_dt}) must be after $start_dt ({self.start_dt})")

        # Validate negative price
        # No validation here, because prices can be occasionally negative - mostly commodities
        # during periods of extreme supply/demand imbalance (electricity / crude oil / gas / ...)

        # Validate high price
        if self.high < self.open or self.high < self.low or self.high < self.close:
            raise ValueError(
                f"$high price ({self.high}) must be greater than or equal to all other prices: open={self.open}, low={self.low}, close={self.close}",
            )

        # Validate low price
        if self.low > self.open or self.low > self.high or self.low > self.close:
            raise ValueError(
                f"$low price ({self.low}) must be less than or equal to all other prices: open={self.open}, high={self.high}, close={self.close}",
            )
