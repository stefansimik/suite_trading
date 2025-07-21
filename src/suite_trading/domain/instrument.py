from decimal import Decimal
from typing import Union


class Instrument:
    """Represents a financial instrument.

    Attributes:
        name (str): The name of the instrument (e.g., "EURUSD").
        exchange (str): The exchange where the instrument is traded (e.g., "FOREX").
        price_increment (Decimal): The minimum price change increment.
        quantity_increment (Decimal): The minimum quantity change increment.
        contract_value_multiplier (Decimal): The value of one contract (e.g., 125000 for 6E on CME).
    """

    def __init__(
        self,
        name: str,
        exchange: str,
        price_increment: Union[Decimal, str, float],
        quantity_increment: Union[Decimal, str, float] = Decimal("1"),
        contract_value_multiplier: Union[Decimal, str, float] = Decimal("1"),
    ):
        """Initialize a new instrument.

        Args:
            name: The name of the instrument (e.g., "EURUSD").
            exchange: The exchange where the instrument is traded (e.g., "FOREX").
            price_increment: The minimum price change increment.
            quantity_increment: The minimum quantity change increment.
            contract_value_multiplier: The value of one contract (e.g., 125000 for 6E on CME).

        Raises:
            ValueError: If any increment values are not positive.
        """
        # Explicit type conversion
        self._name = name
        self._exchange = exchange
        self._price_increment = Decimal(str(price_increment))
        self._quantity_increment = Decimal(str(quantity_increment))
        self._contract_value_multiplier = Decimal(str(contract_value_multiplier))

        # Explicit validation
        if self._price_increment <= 0:
            raise ValueError(f"$price_increment must be positive, but provided value is: {self._price_increment}")
        if self._quantity_increment <= 0:
            raise ValueError(f"$quantity_increment must be positive, but provided value is: {self._quantity_increment}")
        if self._contract_value_multiplier <= 0:
            raise ValueError(f"$contract_value_multiplier must be positive, but provided value is: {self._contract_value_multiplier}")

    @property
    def name(self) -> str:
        """Get the instrument name."""
        return self._name

    @property
    def exchange(self) -> str:
        """Get the exchange name."""
        return self._exchange

    @property
    def price_increment(self) -> Decimal:
        """Get the minimum price change increment."""
        return self._price_increment

    @property
    def quantity_increment(self) -> Decimal:
        """Get the minimum quantity change increment."""
        return self._quantity_increment

    @property
    def contract_value_multiplier(self) -> Decimal:
        """Get the value of one contract."""
        return self._contract_value_multiplier

    def __str__(self) -> str:
        """Return a string representation of the instrument.

        Returns:
            str: The instrument in format "name@exchange".
        """
        return f"{self.name}@{self.exchange}"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the instrument.

        Returns:
            str: A detailed string representation.
        """
        return (
            f"{self.__class__.__name__}(name={self.name!r}, exchange={self.exchange!r}, "
            f"price_increment={self.price_increment}, quantity_increment={self.quantity_increment}, "
            f"contract_value_multiplier={self.contract_value_multiplier})"
        )

    def __eq__(self, other) -> bool:
        """Check equality with another instrument.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if instruments are equal, False otherwise.
        """
        if not isinstance(other, Instrument):
            return False
        return (
            self.name == other.name
            and self.exchange == other.exchange
            and self.price_increment == other.price_increment
            and self.quantity_increment == other.quantity_increment
            and self.contract_value_multiplier == other.contract_value_multiplier
        )

    def __hash__(self) -> int:
        """Return hash value for the instrument.

        This allows Instrument objects to be used as dictionary keys.

        Returns:
            int: Hash value based on all attributes.
        """
        return hash((self.name, self.exchange, self.price_increment, self.quantity_increment, self.contract_value_multiplier))
