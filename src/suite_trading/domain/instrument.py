from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Instrument:
    """Represents a financial instrument.

    Attributes:
        name (str): The name of the instrument (e.g., "EURUSD").
        exchange (str): The exchange where the instrument is traded (e.g., "FOREX").
        price_increment (Decimal): The minimum price change increment.
        quantity_increment (Decimal): The minimum quantity change increment.
        contract_value_multiplier (Decimal): The value of one contract (e.g., 125000 for 6E on CME).
    """

    name: str
    exchange: str
    price_increment: Decimal
    quantity_increment: Decimal = Decimal("1")
    contract_value_multiplier: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        """Validate the instrument data after initialization.

        Raises:
            ValueError: if some data are invalid.
        """
        # Convert values to Decimal if they're not already
        for field in ["price_increment", "quantity_increment", "contract_value_multiplier"]:
            value = getattr(self, field)
            if not isinstance(value, Decimal):
                # set a new converted value (bypass mechanism of frozen dataclass, that does not allow setting new value)
                object.__setattr__(self, field, Decimal(str(value)))

        # Validate increments
        if self.price_increment <= 0:
            raise ValueError("price_increment must be positive")
        if self.quantity_increment <= 0:
            raise ValueError("quantity_increment must be positive")
        if self.contract_value_multiplier <= 0:
            raise ValueError("contract_value_multiplier must be positive")

    def __str__(self) -> str:
        """Return a string representation of the instrument.

        Returns:
            str: The instrument in format "name@exchange".
        """
        return f"{self.name}@{self.exchange}"
