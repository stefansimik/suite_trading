from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.price_type import PriceType


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

    SEPARATOR: str = "::"

    def __init__(self, instrument: Instrument, value: int, unit: BarUnit, price_type: PriceType):
        """Initialize a new bar type.

        Args:
            instrument: The financial instrument.
            value: The numeric value of the period (e.g., 1, 5, 15).
            unit: The unit of the period (e.g., MINUTE, HOUR) from BarUnit.
            price_type: The type of price data (BID/ASK/LAST/MID).
        """
        self._instrument = instrument
        self._value = value
        self._unit = unit
        self._price_type = price_type

    @property
    def instrument(self) -> Instrument:
        """Get the instrument."""
        return self._instrument

    @property
    def value(self) -> int:
        """Get the period value."""
        return self._value

    @property
    def unit(self) -> BarUnit:
        """Get the period unit."""
        return self._unit

    @property
    def price_type(self) -> PriceType:
        """Get the price type."""
        return self._price_type

    def __str__(self) -> str:
        """Return a string representation of the bar type."""
        return f"{str(self.instrument)}{self.SEPARATOR}{self.value}-{self.unit.name}{self.SEPARATOR}{self.price_type.name}"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the bar type.

        Returns:
            str: A detailed string representation.
        """
        return f"{self.__class__.__name__}(instrument={self.instrument!r}, value={self.value}, unit={self.unit}, price_type={self.price_type})"

    def __eq__(self, other) -> bool:
        """Check equality with another bar type.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if bar types are equal, False otherwise.
        """
        if not isinstance(other, BarType):
            return False
        return self.instrument == other.instrument and self.value == other.value and self.unit == other.unit and self.price_type == other.price_type

    def __hash__(self) -> int:
        """Return hash value for the bar type.

        This allows BarType objects to be used as dictionary keys.

        Returns:
            int: Hash value based on all attributes.
        """
        return hash((self.instrument, self.value, self.unit, self.price_type))
