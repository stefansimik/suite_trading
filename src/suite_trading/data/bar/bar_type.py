from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from suite_trading.data.bar.bar_unit import BarUnit
from suite_trading.data.instrument import Instrument
from suite_trading.data.price_type import PriceType


@dataclass(frozen=True)
class BarType:
    """Represents the type of bar.

    Example:
        >>> instrument = Instrument("EURUSD", "FOREX", Decimal("0.00001"), Decimal("1"))
        >>> bar_type = BarType(instrument, 5, BarUnit.MINUTE, PriceType.LAST)
        >>> print(bar_type)
        EURUSD@FOREX::5-MINUTE::LAST

    Attributes:
        instrument: The financial instrument.
        value: The numeric value of the period (e.g., 1, 5, 15).
        unit: The unit of the period (e.g., MINUTE, HOUR) from BarUnit.
        price_type: The type of price data (BID/ASK/LAST/MID).
    """

    instrument: Instrument
    value: int
    unit: BarUnit
    price_type: PriceType

    SEPARATOR: ClassVar[str] = "::"


    def __str__(self) -> str:
        """Return a string representation of the bar type.
        """
        return f"{str(self.instrument)}{self.SEPARATOR}{self.value}-{self.unit.name}{self.SEPARATOR}{self.price_type.name}"
