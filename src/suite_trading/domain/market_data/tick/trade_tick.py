from datetime import datetime
from decimal import Decimal
from typing import Union

from suite_trading.domain.instrument import Instrument
from suite_trading.utils.datetime_utils import format_dt, expect_utc


class TradeTick:
    """Represents a single trade in financial markets.

    A TradeTick contains information about a single executed trade, including
    the instrument, price, volume, and timestamp.

    Attributes:
        instrument (Instrument): The financial instrument.
        price (Decimal): The price at which the trade was executed.
        volume (Decimal): The volume of the trade.
        timestamp (datetime): The datetime when the trade occurred (timezone-aware).
    """

    def __init__(self, instrument: Instrument, price: Union[Decimal, str, float], volume: Union[Decimal, str, float], timestamp: datetime):
        """Initialize a new trade tick.

        Args:
            instrument: The financial instrument.
            price: The price at which the trade was executed.
            volume: The volume of the trade.
            timestamp: The datetime when the trade occurred (timezone-aware).

        Raises:
            ValueError: If trade tick data is invalid.
        """
        # Store instrument and timestamp (validate while assigning)
        self._instrument = instrument
        self._timestamp = expect_utc(timestamp)

        # Explicit type conversion
        self._price = Decimal(str(price))
        self._volume = Decimal(str(volume))

        # Validate volume
        if self._volume <= 0:
            raise ValueError(f"$volume must be positive, but provided value is: {self._volume}")

        # Note: No price validation here, as prices can be negative for some instruments
        # (commodities during extreme supply/demand imbalance)

    @property
    def instrument(self) -> Instrument:
        """Get the instrument."""
        return self._instrument

    @property
    def price(self) -> Decimal:
        """Get the trade price."""
        return self._price

    @property
    def volume(self) -> Decimal:
        """Get the trade volume."""
        return self._volume

    @property
    def timestamp(self) -> datetime:
        """Get the timestamp."""
        return self._timestamp

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.instrument}, {self.price} x {self.volume}, {format_dt(self.timestamp)})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(instrument={self.instrument}, price={self.price}, volume={self.volume}, timestamp={format_dt(self.timestamp)})"

    def __eq__(self, other) -> bool:
        """Check equality with another trade tick.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if trade ticks are equal, False otherwise.
        """
        if not isinstance(other, TradeTick):
            return False
        return self.instrument == other.instrument and self.price == other.price and self.volume == other.volume and self.timestamp == other.timestamp
