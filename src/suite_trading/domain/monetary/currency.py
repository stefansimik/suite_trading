from enum import Enum
from typing import Dict


class CurrencyType(Enum):
    """Enumeration of currency types."""

    FIAT = "FIAT"
    CRYPTO = "CRYPTO"
    COMMODITY = "COMMODITY"


class Currency:
    """Represents a currency with code, precision, and metadata.

    Attributes:
        code (str): Currency code (e.g., "USD", "BTC").
        precision (int): Number of decimal places (0-16).
        name (str): Full currency name.
        currency_type (CurrencyType): Type of currency (FIAT, CRYPTO, COMMODITY).
    """

    # Class-level registry for predefined currencies
    _registry: Dict[str, "Currency"] = {}

    def __init__(self, code: str, precision: int, name: str, currency_type: CurrencyType):
        """Initialize a Currency instance.

        Args:
            code (str): Currency code (e.g., "USD", "BTC").
            precision (int): Number of decimal places (0-16).
            name (str): Full currency name.
            currency_type (CurrencyType): Type of currency.

        Raises:
            ValueError: If parameters are invalid.
            TypeError: If currency_type is not CurrencyType instance.
        """
        # Validate inputs
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"$code must be a non-empty string, but provided value is: '{code}'")

        if not isinstance(precision, int) or precision < 0 or precision > 18:
            raise ValueError(f"$precision must be an integer between 0 and 18, but provided value is: {precision}")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"$name must be a non-empty string, but provided value is: '{name}'")

        if not isinstance(currency_type, CurrencyType):
            raise TypeError(f"$currency_type must be a CurrencyType instance, but provided value is: {currency_type}")

        self._code = code.upper().strip()
        self._precision = precision
        self._name = name.strip()
        self._currency_type = currency_type

    @property
    def code(self) -> str:
        """Get the currency code."""
        return self._code

    @property
    def precision(self) -> int:
        """Get the currency precision."""
        return self._precision

    @property
    def name(self) -> str:
        """Get the currency name."""
        return self._name

    @property
    def currency_type(self) -> CurrencyType:
        """Get the currency type."""
        return self._currency_type

    @classmethod
    def register(cls, currency: "Currency", overwrite: bool = False) -> None:
        """Register a currency in the global registry.

        Args:
            currency (Currency): The currency to register.
            overwrite (bool): Whether to overwrite existing currency.

        Raises:
            ValueError: If currency already exists and overwrite is False.
            TypeError: If currency is not Currency instance.
        """
        if not isinstance(currency, Currency):
            raise TypeError(f"$currency must be a Currency instance, but provided value is: {currency}")

        if currency.code in cls._registry and not overwrite:
            raise ValueError(f"Currency with code '{currency.code}' already exists in registry. Use overwrite=True to replace it.")

        cls._registry[currency.code] = currency

    @classmethod
    def from_str(cls, code: str) -> "Currency":
        """Get currency from registry by code.

        Args:
            code (str): Currency code to look up.

        Returns:
            Currency: The currency instance.

        Raises:
            ValueError: If currency code is not found in registry.
        """
        if not isinstance(code, str):
            raise TypeError(f"$code must be a string, but provided value is: {code}")

        code = code.upper().strip()
        if code not in cls._registry:
            raise ValueError(f"Currency with code '{code}' not found in registry. Available currencies: {list(cls._registry.keys())}")

        return cls._registry[code]

    @property
    def is_fiat(self) -> bool:
        """Check if currency is fiat.

        Returns:
            bool: True if currency is fiat.
        """
        return self._currency_type == CurrencyType.FIAT

    @property
    def is_crypto(self) -> bool:
        """Check if currency is cryptocurrency.

        Returns:
            bool: True if currency is cryptocurrency.
        """
        return self._currency_type == CurrencyType.CRYPTO

    @property
    def is_commodity(self) -> bool:
        """Check if currency is commodity.

        Returns:
            bool: True if currency is commodity.
        """
        return self._currency_type == CurrencyType.COMMODITY

    def __eq__(self, other) -> bool:
        """Check equality with another Currency."""
        if not isinstance(other, Currency):
            return False
        return self.code == other.code

    def __hash__(self) -> int:
        """Hash based on currency code."""
        return hash(self.code)

    def __str__(self) -> str:
        """Return string representation."""
        return self.code

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return f"{self.__class__.__name__}('{self.code}', {self.precision}, '{self.name}', {self.currency_type})"
