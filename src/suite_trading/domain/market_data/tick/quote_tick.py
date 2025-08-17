from datetime import datetime
from decimal import Decimal
from typing import Union

from suite_trading.domain.instrument import Instrument
from suite_trading.utils.datetime_utils import format_dt


class QuoteTick:
    """Represents a market quote in financial markets.

    A QuoteTick contains information about the best bid and ask prices and volumes
    for a specific instrument at a specific point in time.

    Attributes:
        instrument (Instrument): The financial instrument.
        bid_price (Decimal): The best bid price (highest price a buyer is willing to pay).
        ask_price (Decimal): The best ask price (lowest price a seller is willing to accept).
        bid_volume (Decimal): The volume available at the best bid price.
        ask_volume (Decimal): The volume available at the best ask price.
        timestamp (datetime): The datetime when the quote was recorded (timezone-aware).
    """

    def __init__(
        self,
        instrument: Instrument,
        bid_price: Union[Decimal, str, float],
        ask_price: Union[Decimal, str, float],
        bid_volume: Union[Decimal, str, float],
        ask_volume: Union[Decimal, str, float],
        timestamp: datetime,
    ):
        """Initialize a new quote tick.

        Args:
            instrument: The financial instrument.
            bid_price: The best bid price (highest price a buyer is willing to pay).
            ask_price: The best ask price (lowest price a seller is willing to accept).
            bid_volume: The volume available at the best bid price.
            ask_volume: The volume available at the best ask price.
            timestamp: The datetime when the quote was recorded (timezone-aware).

        Raises:
            ValueError: If quote tick data is invalid.
        """
        # Store instrument and timestamp
        self._instrument = instrument
        self._timestamp = timestamp

        # Explicit type conversion
        self._bid_price = Decimal(str(bid_price))
        self._ask_price = Decimal(str(ask_price))
        self._bid_volume = Decimal(str(bid_volume))
        self._ask_volume = Decimal(str(ask_volume))

        # Explicit validation
        # Ensure timestamp is timezone-aware
        if self._timestamp.tzinfo is None:
            raise ValueError(f"$timestamp must be timezone-aware, but provided value is: {self._timestamp}")

        # Validate volumes
        if self._bid_volume <= 0:
            raise ValueError(f"$bid_volume must be positive, but provided value is: {self._bid_volume}")
        if self._ask_volume <= 0:
            raise ValueError(f"$ask_volume must be positive, but provided value is: {self._ask_volume}")

        # Validate prices
        if self._bid_price <= 0:
            raise ValueError(f"$bid_price must be positive, but provided value is: {self._bid_price}")
        if self._ask_price <= 0:
            raise ValueError(f"$ask_price must be positive, but provided value is: {self._ask_price}")
        if self._bid_price >= self._ask_price:
            raise ValueError(f"$bid_price ({self._bid_price}) must be less than $ask_price ({self._ask_price})")

    @property
    def instrument(self) -> Instrument:
        """Get the instrument."""
        return self._instrument

    @property
    def bid_price(self) -> Decimal:
        """Get the bid price."""
        return self._bid_price

    @property
    def ask_price(self) -> Decimal:
        """Get the ask price."""
        return self._ask_price

    @property
    def bid_volume(self) -> Decimal:
        """Get the bid volume."""
        return self._bid_volume

    @property
    def ask_volume(self) -> Decimal:
        """Get the ask volume."""
        return self._ask_volume

    @property
    def timestamp(self) -> datetime:
        """Get the timestamp."""
        return self._timestamp

    def __str__(self) -> str:
        """Return a string representation of the quote tick.

        Returns:
            str: A human-readable string representation.
        """
        ts = format_dt(self.timestamp)
        return f"{self.__class__.__name__}({self.instrument}, {self.bid_price}x{self.bid_volume} / {self.ask_price}x{self.ask_volume}, {ts})"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the quote tick.

        Returns:
            str: A detailed string representation.
        """
        return f"{self.__class__.__name__}(instrument={self.instrument!r}, bid_price={self.bid_price}, ask_price={self.ask_price}, bid_volume={self.bid_volume}, ask_volume={self.ask_volume}, timestamp={self.timestamp!r})"

    def __eq__(self, other) -> bool:
        """Check equality with another quote tick.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if quote ticks are equal, False otherwise.
        """
        if not isinstance(other, QuoteTick):
            return False
        return self.instrument == other.instrument and self.bid_price == other.bid_price and self.ask_price == other.ask_price and self.bid_volume == other.bid_volume and self.ask_volume == other.ask_volume and self.timestamp == other.timestamp
