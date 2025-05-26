from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from suite_trading.data.instrument import Instrument

@dataclass(frozen=True)
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

    instrument: Instrument
    price: Decimal
    volume: Decimal
    timestamp: datetime

    def __post_init__(self) -> None:
        """Validate the trade tick data after initialization.

        Raises:
            ValueError: if some data are invalid.
        """
        # Convert values to Decimal if they're not already
        for field in ["price", "volume"]:
            value = getattr(self, field)
            if not isinstance(value, Decimal):
                # set a new converted value (bypass mechanism of frozen dataclass, that does not allow setting new value)
                object.__setattr__(self, field, Decimal(str(value)))

        # Ensure timestamp is timezone-aware
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

        # Validate volume
        if self.volume <= 0:
            raise ValueError("volume must be positive")
