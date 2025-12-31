from __future__ import annotations

from decimal import Decimal, getcontext, InvalidOperation

from suite_trading.domain.monetary.currency import Currency
from suite_trading.utils.numeric_tools import DecimalLike, as_decimal

# Set high precision for financial calculations
getcontext().prec = 28


class Money:
    """Represents a monetary amount with currency.

    Uses Python's Decimal for precision arithmetic.
    Supports values between -999_999_999_999_999.999999999999999999 and
    +999_999_999_999_999.999999999999999999
    """

    # Value limits
    MAX_VALUE = Decimal("999_999_999_999_999.999999999999999999")
    MIN_VALUE = Decimal("-999_999_999_999_999.999999999999999999")

    def __init__(self, value: DecimalLike, currency: Currency):
        """Initialize Money with value and currency.

        Args:
            value: Numeric value (Decimal-like scalar).
            currency (Currency): Currency object.

        Raises:
            ValueError: If value is invalid or out of range.
            TypeError: If currency is not Currency instance.
        """
        # Raise: currency must be an instance of Currency
        if not isinstance(currency, Currency):
            raise TypeError(f"$currency must be a Currency instance, but provided value is: {currency}")

        # Raise: $value must be convertible to Decimal
        try:
            decimal_value = as_decimal(value)
        except (ValueError, TypeError, InvalidOperation) as e:
            raise ValueError(f"Cannot init `Money` because $value ({value}) cannot be converted to Decimal") from e

        # Raise: value must be within allowed range
        if decimal_value > self.MAX_VALUE:
            raise ValueError(f"$value exceeds maximum allowed value {self.MAX_VALUE}, but provided value is: {decimal_value}")
        if decimal_value < self.MIN_VALUE:
            raise ValueError(f"$value is below minimum allowed value {self.MIN_VALUE}, but provided value is: {decimal_value}")

        # Round to currency precision
        precision_str = f"0.{'0' * currency.precision}" if currency.precision > 0 else "1"
        self._value = decimal_value.quantize(Decimal(precision_str))
        self._currency = currency

    @property
    def value(self) -> Decimal:
        """Get the decimal value."""
        return self._value

    @property
    def currency(self) -> Currency:
        """Get the currency."""
        return self._currency

    def clamp(self, lower: DecimalLike | None = None, upper: DecimalLike | None = None) -> Money:
        """Return a new Money with $value clamped into [$lower, $upper].

        Currency always stays the same as $self.currency.

        Args:
            lower: Optional lower bound for $value. If None, there is no lower bound.
            upper: Optional upper bound for $value. If None, there is no upper bound.

        Returns:
            Money: New instance with value clamped into the requested range.

        Raises:
            ValueError: If both bounds are provided and $lower > $upper.
            ValueError: If a bound cannot be converted to Decimal.
        """

        try:
            lower_value = as_decimal(lower) if lower is not None else None
        except (ValueError, TypeError, InvalidOperation) as e:
            raise ValueError(f"Cannot call `clamp` because $lower ({lower}) cannot be converted to Decimal") from e

        try:
            upper_value = as_decimal(upper) if upper is not None else None
        except (ValueError, TypeError, InvalidOperation) as e:
            raise ValueError(f"Cannot call `clamp` because $upper ({upper}) cannot be converted to Decimal") from e

        # Raise: ensure the requested range is not inverted
        if lower_value is not None and upper_value is not None and lower_value > upper_value:
            raise ValueError(f"Cannot call `clamp` because $lower ({lower_value}) > $upper ({upper_value})")

        new_value = self.value
        if lower_value is not None:
            new_value = max(new_value, lower_value)
        if upper_value is not None:
            new_value = min(new_value, upper_value)

        result = self.__class__(new_value, self.currency)
        return result

    def _check_same_currency(self, other: Money) -> None:
        """Check if two Money objects have the same currency.

        Args:
            other (Money): The other Money object.

        Raises:
            ValueError: If currencies don't match.
        """
        if self.currency != other.currency:
            raise ValueError(f"Cannot operate on different currencies: {self.currency} and {other.currency}")

    # Comparison operators (same currency required)
    def __eq__(self, other) -> bool:
        """Check equality with another Money object."""
        if not isinstance(other, Money):
            return False
        if self.currency != other.currency:
            return False
        return self.value == other.value

    def __lt__(self, other) -> bool:
        """Check if this Money is less than another Money object."""
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self.value < other.value

    def __le__(self, other) -> bool:
        """Check if this Money is less than or equal to another Money object."""
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self.value <= other.value

    def __gt__(self, other) -> bool:
        """Check if this Money is greater than another Money object."""
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self.value > other.value

    def __ge__(self, other) -> bool:
        """Check if this Money is greater than or equal to another Money object."""
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self.value >= other.value

    # Arithmetic operations
    def __add__(self, other):
        """Add two Money objects (same currency) or Money + number."""
        if isinstance(other, Money):
            self._check_same_currency(other)
            return Money(self.value + other.value, self.currency)
        else:
            # Add number to Money
            try:
                return Money(self.value + as_decimal(other), self.currency)
            except (ValueError, TypeError):
                return NotImplemented

    def __radd__(self, other):
        """Right addition: number + Money."""
        return self.__add__(other)

    def __sub__(self, other):
        """Subtract two Money objects (same currency) or Money - number."""
        if isinstance(other, Money):
            self._check_same_currency(other)
            return Money(self.value - other.value, self.currency)
        else:
            # Subtract number from Money
            try:
                return Money(self.value - as_decimal(other), self.currency)
            except (ValueError, TypeError):
                return NotImplemented

    def __rsub__(self, other):
        """Right subtraction: number - Money."""
        try:
            return Money(as_decimal(other) - self.value, self.currency)
        except (ValueError, TypeError):
            return NotImplemented

    def __mul__(self, other):
        """Multiply Money by number (returns Money)."""
        if isinstance(other, Money):
            return NotImplemented  # Money * Money doesn't make sense
        try:
            return Money(self.value * as_decimal(other), self.currency)
        except (ValueError, TypeError):
            return NotImplemented

    def __rmul__(self, other):
        """Right multiplication: number * Money."""
        return self.__mul__(other)

    def __truediv__(self, other):
        """Divide Money by number (returns Money) or Money by Money (returns Decimal)."""
        if isinstance(other, Money):
            self._check_same_currency(other)
            if other.value == 0:
                raise ZeroDivisionError("Cannot divide by zero Money")
            return self.value / other.value
        else:
            try:
                divisor = as_decimal(other)
                if divisor == 0:
                    raise ZeroDivisionError("Cannot divide Money by zero")
                return Money(self.value / divisor, self.currency)
            except (ValueError, TypeError):
                return NotImplemented

    def __rtruediv__(self, other):
        """Right division: number / Money (not supported)."""
        return NotImplemented

    def __neg__(self):
        return Money(-self.value, self.currency)

    def __pos__(self):
        return Money(self.value, self.currency)

    def __abs__(self):
        return Money(abs(self.value), self.currency)

    # String representations
    def __str__(self) -> str:
        """Return string like '1000.50 USD'."""
        return f"{self.value} {self.currency.code}"

    def __repr__(self) -> str:
        """Return string like 'Money(1000.50, USD)'."""
        return f"{self.__class__.__name__}({self.value}, {self.currency.code})"

    def __hash__(self) -> int:
        """Hash based on value and currency code."""
        return hash((self.value, self.currency.code))

    @classmethod
    def from_str(cls, value_str: str) -> Money:
        """Parse Money from string like '1000.50 USD'.

        Args:
            value_str (str): String representation.

        Returns:
            Money: Money object.

        Raises:
            ValueError: If string format is invalid.
        """
        value_str = value_str.strip()
        if not value_str:
            raise ValueError("Value string with $value_str = '' cannot be empty")

        # Split by whitespace
        parts = value_str.split()
        if len(parts) != 2:
            raise ValueError(f"Value string with $value_str = '{value_str}' must be in format 'value currency_code'")

        value_part, currency_part = parts

        try:
            value = Decimal(value_part)
        except (ValueError, TypeError, InvalidOperation) as e:
            raise ValueError(f"Invalid value part '{value_part}' in string '{value_str}'") from e

        try:
            currency = Currency.from_str(currency_part)
        except ValueError as e:
            raise ValueError(f"Invalid currency part '{currency_part}' in string '{value_str}'") from e

        return cls(value, currency)
