from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.suite_trading.domain.event import Event
from suite_trading.domain.instrument import Instrument


@dataclass(frozen=True)
class TradeTick(Event):
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
    dt_received: Optional[datetime] = None

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
            raise ValueError(f"$timestamp must be timezone-aware, but provided value is: {self.timestamp}")

        # Validate volume
        if self.volume <= 0:
            raise ValueError(f"$volume must be positive, but provided value is: {self.volume}")

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the trade occurred.

        For trade ticks, the event time is the timestamp when the trade was executed.

        Returns:
            datetime: The trade timestamp.
        """
        return self.timestamp

    @property
    def event_type(self) -> str:
        """Type identifier for the trade tick event.

        Returns:
            str: Always returns "trade_tick" for TradeTick objects.
        """
        return "trade_tick"
