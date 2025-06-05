from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from suite_trading.domain.instrument import Instrument


@dataclass(frozen=True)
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

    instrument: Instrument
    bid_price: Decimal
    ask_price: Decimal
    bid_volume: Decimal
    ask_volume: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        """Validate the quote tick data after initialization.

        Raises:
            ValueError: if some data are invalid.
        """
        # Convert values to Decimal if they're not already
        for field in ["bid_price", "ask_price", "bid_volume", "ask_volume"]:
            value = getattr(self, field)
            if not isinstance(value, Decimal):
                # set a new converted value (bypass mechanism of frozen dataclass, that does not allow setting new value)
                object.__setattr__(self, field, Decimal(str(value)))

        # Ensure timestamp is timezone-aware
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

        # Validate volumes
        if self.bid_volume <= 0:
            raise ValueError("bid_volume must be positive")
        if self.ask_volume <= 0:
            raise ValueError("ask_volume must be positive")

        # Validate prices
        if self.bid_price <= 0:
            raise ValueError("bid_price must be positive")
        if self.ask_price <= 0:
            raise ValueError("ask_price must be positive")
        if self.bid_price >= self.ask_price:
            raise ValueError("bid_price must be less than ask_price")
