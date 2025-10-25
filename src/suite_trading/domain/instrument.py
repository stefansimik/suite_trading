from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN


class Instrument:
    """Represents a financial instrument.

    Attributes:
        name (str): The name of the instrument (e.g., "EURUSD").
        exchange (str): The exchange where the instrument is traded (e.g., "FOREX").
        price_increment (Decimal): The minimum price change increment.
        quantity_increment (Decimal): The minimum quantity change increment.
        contract_value_multiplier (Decimal): The value of one contract (e.g., 125000 for 6E on CME).
    """

    __slots__ = (
        "_name",
        "_exchange",
        "_price_increment",
        "_quantity_increment",
        "_contract_value_multiplier",
    )

    def __init__(
        self,
        name: str,
        exchange: str,
        price_increment: Decimal | str,
        quantity_increment: Decimal | str = Decimal("1"),
        contract_value_multiplier: Decimal | str = Decimal("1"),
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

    # region Convenience

    def ticks_to_price(self, tick_count: int) -> Decimal:
        """Return price delta for $tick_count ticks as an exact Decimal.

        Args:
            tick_count: Tick count; can be negative, zero, or positive.

        Returns:
            Decimal: Exact price change computed as `tick_count * price_increment`.

        Raises:
            TypeError: If $tick_count is not an int.
        """
        # Check: enforce integer tick count for predictable arithmetic
        if not isinstance(tick_count, int):
            raise TypeError("Cannot call `ticks_to_price` because $tick_count is not int. Pass an int for tick count.")
        # Return the price delta; negative and zero are allowed
        return self.price_increment * tick_count

    def price_to_ticks(self, price_delta: Decimal) -> int:
        """Return the number of whole ticks represented by $price_delta.

        The result is signed and computed as `price_delta / price_increment`.

        Args:
            price_delta (Decimal): Price delta to convert to ticks.

        Returns:
            int: Signed tick count.

        Raises:
            TypeError: If $price_delta is not Decimal.
            ValueError: If $price_delta is not finite or not a multiple of $price_increment.
        """
        # Check: enforce Decimal input to avoid silent float issues
        if not isinstance(price_delta, Decimal):
            raise TypeError("Cannot call `price_to_ticks` because $price_delta must be Decimal")

        # Check: input must be finite
        if not price_delta.is_finite():
            raise ValueError(f"Cannot call `price_to_ticks` because $price_delta ('{price_delta}') is not finite")

        # Check: price_delta must align to the instrument's tick size
        if price_delta % self.price_increment != 0:
            raise ValueError(f"Cannot call `price_to_ticks` because $price_delta ('{price_delta}') is not a multiple of $price_increment ('{self.price_increment}')")

        ticks = price_delta / self.price_increment
        return int(ticks)

    def quantity_from_lots(self, n: int) -> Decimal:
        """Return a quantity equal to $n quantity_from_lots (n * $quantity_increment).

        Note: "lot" denotes the standardized minimal tradable unit for the Instrument.

        Args:
            n (int): Number of lot units. Must be a positive integer.

        Returns:
            Decimal: Exact quantity as `n * quantity_increment`.

        Raises:
            TypeError: If $n is not an int.
            ValueError: If $n <= 0.
        """
        # Check: enforce integer count of quantity_from_lots for predictable arithmetic
        if not isinstance(n, int):
            raise TypeError("Cannot call `quantity_from_lots` because $n is not int. Pass a positive int for lot count.")

        # Check: quantity_from_lots must be positive to express a non-zero quantity
        if n <= 0:
            raise ValueError(f"Cannot call `quantity_from_lots` because $n ('{n}') must be > 0.")

        # Return the quantity
        return self.quantity_increment * n

    # endregion

    # region Normalization

    def snap_price(self, value: Decimal | str | float | int) -> Decimal:
        """Return $value snapped to $price_increment as an exact Decimal.

        Accepts float safely by converting via str(...) before Decimal construction, then
        quantizes to $price_increment using banker’s rounding (ROUND_HALF_EVEN).

        Args:
            value: Price to normalize (Decimal, str, int, or float).

        Returns:
            Decimal: Price snapped to a multiple of $price_increment.

        Raises:
            ValueError: If $value <= 0.
        """
        # Convert safely; avoid binary float artifacts by using str(...) for non-Decimal
        v = value if isinstance(value, Decimal) else Decimal(str(value))

        # Check: price must be positive for trading semantics
        if v <= 0:
            raise ValueError(f"Cannot call `snap_price` because $value ('{v}') must be > 0.")

        # Snap to the instrument's price increment (banker's rounding)
        return v.quantize(self.price_increment, rounding=ROUND_HALF_EVEN)

    def snap_quantity(self, value: Decimal | str | float | int) -> Decimal:
        """Return $value snapped to $quantity_increment as an exact Decimal.

        Accepts float safely by converting via str(...) before Decimal construction, then
        quantizes to $quantity_increment using banker’s rounding (ROUND_HALF_EVEN).

        Args:
            value: Quantity to normalize (Decimal, str, int, or float).

        Returns:
            Decimal: Quantity snapped to a multiple of $quantity_increment.

        Raises:
            ValueError: If $value <= 0.
        """
        # Convert safely; avoid binary float artifacts by using str(...) for non-Decimal
        v = value if isinstance(value, Decimal) else Decimal(str(value))

        # Check: quantity must be positive for trading semantics
        if v <= 0:
            raise ValueError(f"Cannot call `snap_quantity` because $value ('{v}') must be > 0.")

        # Snap to the instrument's quantity increment (banker's rounding)
        return v.quantize(self.quantity_increment, rounding=ROUND_HALF_EVEN)

    # endregion

    # region Special methods

    def __str__(self) -> str:
        """Return a concise string representation of the instrument.

        Returns:
            str: The instrument in format "<name>@<exchange>" (e.g., "EURUSD@FOREX").
        """
        return f"{self.name}@{self.exchange}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, exchange={self.exchange}, price_increment={self.price_increment}, quantity_increment={self.quantity_increment}, contract_value_multiplier={self.contract_value_multiplier})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Instrument):
            return False
        return self.name == other.name and self.exchange == other.exchange and self.price_increment == other.price_increment and self.quantity_increment == other.quantity_increment and self.contract_value_multiplier == other.contract_value_multiplier

    def __hash__(self) -> int:
        """Return hash value for the instrument.

        This allows Instrument objects to be used as dictionary keys.

        Returns:
            int: Hash value based on all attributes.
        """
        return hash((self.name, self.exchange, self.price_increment, self.quantity_increment, self.contract_value_multiplier))

    # endregion
