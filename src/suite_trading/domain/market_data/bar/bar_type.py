from __future__ import annotations

from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.price_type import PriceType


class BarType:
    """Represents the type of bar.

    Example:
        >>> instrument = Instrument("EURUSD", "FOREX", Decimal("0.00001"), Decimal("1"))
        >>> bar_type = BarType(instrument, 5, BarUnit.MINUTE, PriceType.LAST_TRADE)
        >>> print(bar_type)
        EURUSD@FOREX::5-MINUTE::LAST_TRADE

    Attributes:
        instrument: The financial instrument.
        value: The numeric value of the period (e.g., 1, 5, 15).
        unit: The unit of the period (e.g., MINUTE, HOUR) from BarUnit.
        price_type: The type of original higher-resolution price data used to build bars
            of this BarType (BID/ASK/MID/LAST_TRADE). LAST_TRADE denotes the last traded
            price (often called LAST by data vendors).
    """

    SEPARATOR: str = "::"

    # region Init

    def __init__(self, instrument: Instrument, value: int, unit: BarUnit, price_type: PriceType):
        """Initialize a new bar type.

        Args:
            instrument: The financial instrument.
            value: The numeric value of the period (e.g., 1, 5, 15).
            unit: The unit of the period (e.g., MINUTE, HOUR) from BarUnit.
            price_type: The type of original higher-resolution price data
                (BID/ASK/MID/LAST_TRADE). LAST_TRADE means the last traded price
                (often called LAST).
        """
        self._instrument = instrument
        self._value = value
        self._unit = unit
        self._price_type = price_type

    # endregion

    # region Convenience

    def copy(
        self,
        *,
        instrument: Instrument | None = None,
        value: int | None = None,
        unit: BarUnit | None = None,
        price_type: PriceType | None = None,
    ) -> BarType:
        """Return a new BarType copied from this instance with optional overrides.

        Args:
            instrument: Optional override for $instrument. If None, reuse current.
            value: Optional override for $value. If None, reuse current.
            unit: Optional override for $unit. If None, reuse current.
            price_type: Optional override for $price_type. If None, reuse current.

        Returns:
            BarType: A new BarType with provided overrides applied.

        Example:
            >>> bt1 = BarType(instrument, 5, BarUnit.MINUTE, PriceType.LAST_TRADE)
            >>> bt2 = bt1.copy(value=15)
            >>> str(bt1)
            'EURUSD@FOREX::5-MINUTE::LAST_TRADE'
            >>> str(bt2)
            'EURUSD@FOREX::15-MINUTE::LAST_TRADE'
        """
        # Create a new instance, reusing current values when overrides are not provided.
        return BarType(
            instrument=instrument if instrument is not None else self.instrument,
            value=value if value is not None else self.value,
            unit=unit if unit is not None else self.unit,
            price_type=price_type if price_type is not None else self.price_type,
        )

    # endregion

    # region Properties

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
        """Return the $price_type indicating which input price series bars use.

        Values: BID, ASK, MID, LAST_TRADE. LAST_TRADE denotes the last traded price
        (often called LAST by data vendors).
        """
        return self._price_type

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.instrument.name}@{self.instrument.exchange}{self.SEPARATOR}{self.value}-{self.unit.name}{self.SEPARATOR}{self.price_type.name}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(instrument={self.instrument}, value={self.value}, unit={self.unit}, price_type={self.price_type})"

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

    # endregion
