from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum
from suite_trading.domain.monetary.currency import Currency
from suite_trading.domain.monetary.money import Money
from suite_trading.utils.numeric_tools import DecimalLike, as_decimal


class AssetClass(Enum):
    """High-level instrument categories used throughout the engine.

    Keep short; add new values only when really needed (YAGNI).
    """

    EQUITY = "EQUITY"
    ETF = "ETF"
    INDEX = "INDEX"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    COMMODITY_SPOT = "COMMODITY_SPOT"
    CRYPTO_SPOT = "CRYPTO_SPOT"
    FX_SPOT = "FX_SPOT"
    BOND = "BOND"


class Instrument:
    """Represents a financial instrument.

    Attributes:
        name (str): The instrument identifier (e.g., "EURUSD", "6E", "AAPL").
        exchange (str): Venue where the instrument is traded (e.g., "FOREX", "CME").
        price_increment (Decimal): Minimum price tick size.
        qty_increment (Decimal): Minimum absolute quantity increment.
        contract_size (Decimal): Underlying amount per contract/lot (e.g., 125000 for 6E).
        contract_unit (str): Unit of the underlying (e.g., "EUR", "share", "barrel", "troy_oz").
        quote_currency (Currency): Currency prices are quoted in (denominator of quote).
        settlement_currency (Currency): Currency where P/L settles.
    """

    __slots__ = (
        "_name",
        "_exchange",
        "_asset_class",
        "_price_increment",
        "_qty_increment",
        "_contract_size",
        "_contract_unit",
        "_quote_currency",
        "_settlement_currency",
    )

    def __init__(
        self,
        name: str,
        exchange: str,
        asset_class: AssetClass,
        price_increment: DecimalLike,
        qty_increment: DecimalLike,
        contract_size: DecimalLike,
        contract_unit: str,
        quote_currency: Currency,
        settlement_currency: Currency | None = None,
    ) -> None:
        """Initialize a new Instrument with explicit currencies and contract spec.

        Args:
            name: The instrument identifier (e.g., "6E", "EURUSD", "AAPL").
            exchange: Venue name (e.g., "CME", "FOREX", "NASDAQ").
            price_increment: Minimum price tick size as a Decimal-like scalar.
            qty_increment: Minimum absolute quantity increment as a Decimal-like scalar.
            contract_size: Underlying amount per contract/lot (e.g., 125000 for 6E) as a Decimal-like scalar.
            contract_unit: Unit of the underlying (e.g., "EUR", "share", "barrel").
            quote_currency: Currency in which prices are quoted (denominator of the quote). This
                expresses how the price is displayed/traded (e.g., USD in EURUSD = 1.1000 USD per 1 EUR).
            settlement_currency: Currency where cash flows and P/L settle (valuation/payoff currency).
                If not provided, defaults to $quote_currency. Use explicitly when settlement differs
                (e.g., inverse crypto, NDF, quanto). Example: The price is shown in USD (USD per 1 BTC),
                but P/L settles in BTC.

        Raises:
            ValueError: If increments or $contract_size are not positive, or $contract_unit is empty.
        """
        # Explicit type conversion
        self._name = name
        self._exchange = exchange
        self._asset_class = asset_class
        self._price_increment = as_decimal(price_increment)
        self._qty_increment = as_decimal(qty_increment)
        self._contract_size = as_decimal(contract_size)
        self._contract_unit = contract_unit

        # Raise: ensure $quote_currency is Currency to keep domain model typed and fail fast during migration
        if not isinstance(quote_currency, Currency):
            raise TypeError(f"Cannot call `Instrument.__init__` because $quote_currency is not Currency (got type '{type(quote_currency).__name__}'). Convert at the boundary using `Currency.from_str`")

        # Raise: ensure $settlement_currency is Currency when provided (defaults to $quote_currency)
        if settlement_currency is not None and not isinstance(settlement_currency, Currency):
            raise TypeError(f"Cannot call `Instrument.__init__` because $settlement_currency is not Currency (got type '{type(settlement_currency).__name__}'). Pass None for default or convert at the boundary")

        self._quote_currency = quote_currency
        self._settlement_currency = self._quote_currency if settlement_currency is None else settlement_currency

        # Raise: $price_increment must be positive to define a valid tick size
        if self._price_increment <= 0:
            raise ValueError(f"Cannot call `Instrument.__init__` because $price_increment ({self._price_increment}) <= 0")

        # Raise: $qty_increment must be positive to define a valid lot size
        if self._qty_increment <= 0:
            raise ValueError(f"Cannot call `Instrument.__init__` because $qty_increment ({self._qty_increment}) <= 0")

        # Raise: $contract_size must be positive to define the contract/lot amount
        if self._contract_size <= 0:
            raise ValueError(f"Cannot call `Instrument.__init__` because $contract_size ({self._contract_size}) <= 0")

        # Raise: $contract_unit must be a non-empty string to describe the underlying unit
        if not isinstance(self._contract_unit, str) or not self._contract_unit.strip():
            raise ValueError("Cannot call `Instrument.__init__` because $contract_unit is empty")

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
    def qty_increment(self) -> Decimal:
        """Get the minimum absolute quantity change increment."""
        return self._qty_increment

    @property
    def contract_size(self) -> Decimal:
        """Get the underlying amount per 1 contract/lot as Decimal."""
        return self._contract_size

    @property
    def contract_unit(self) -> str:
        """Get the unit of the underlying (e.g., 'EUR', 'share', 'barrel')."""
        return self._contract_unit

    @property
    def quote_currency(self) -> Currency:
        """Get the currency prices are quoted in (denominator of the quote)."""
        return self._quote_currency

    @property
    def settlement_currency(self) -> Currency:
        """Get the currency where P/L settles for this Instrument."""
        return self._settlement_currency

    @property
    def asset_class(self) -> AssetClass:
        """Get the asset class of this Instrument."""
        return self._asset_class

    def compute_tick_value(self) -> Money:
        """Return tick value as Money in $settlement_currency for 1 contract and 1 tick."""
        tick_amount = self.contract_size * self.price_increment
        return Money(tick_amount, self.settlement_currency)

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
        # Raise: enforce integer tick count for predictable arithmetic
        if not isinstance(tick_count, int):
            raise TypeError("Cannot call `ticks_to_price` because $tick_count is not int. Pass an int for tick count.")

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
        # Raise: enforce Decimal input to avoid silent float issues
        if not isinstance(price_delta, Decimal):
            raise TypeError("Cannot call `price_to_ticks` because $price_delta must be Decimal")

        # Raise: input must be finite
        if not price_delta.is_finite():
            raise ValueError(f"Cannot call `price_to_ticks` because $price_delta ('{price_delta}') is not finite")

        # Raise: $price_delta must align to the instrument's tick size
        if price_delta % self.price_increment != 0:
            raise ValueError(f"Cannot call `price_to_ticks` because $price_delta ('{price_delta}') is not a multiple of $price_increment ('{self.price_increment}')")

        ticks = price_delta / self.price_increment
        return int(ticks)

    def qty_from_lots(self, n: int) -> Decimal:
        """Return an absolute quantity equal to $n lots (n * $qty_increment).

        Note: "lot" denotes the standardized minimal tradable unit for the Instrument.

        Args:
            n (int): Number of lot units. Must be a positive integer.

        Returns:
            Decimal: Exact absolute quantity as `n * qty_increment`.

        Raises:
            TypeError: If $n is not an int.
            ValueError: If $n <= 0.
        """
        # Raise: enforce integer lot count for predictable arithmetic
        if not isinstance(n, int):
            raise TypeError("Cannot call `qty_from_lots` because $n is not int. Pass a positive int for lot count.")

        # Raise: lot count must be positive to express a non-zero absolute quantity
        if n <= 0:
            raise ValueError(f"Cannot call `qty_from_lots` because $n ('{n}') must be > 0.")

        return self.qty_increment * n

    # endregion

    # region Normalization

    def snap_price(self, value: DecimalLike) -> Decimal:
        """Return $value snapped to $price_increment as an exact Decimal.

        Accepts float safely by converting via `as_decimal` (which uses str(...) for non-Decimal),
        then quantizes to $price_increment using banker’s rounding (ROUND_HALF_EVEN).

        Args:
            value: Price to normalize (Decimal-like scalar).

        Returns:
            Decimal: Price snapped to a multiple of $price_increment.

        Raises:
            ValueError: If $value is not finite.
        """
        # Convert safely; avoid binary float artifacts by using str(...) for non-Decimal
        v = as_decimal(value)

        # Raise: input must be finite; negative prices may be valid in some markets
        if not v.is_finite():
            raise ValueError(f"Cannot call `snap_price` because $value ('{v}') is not finite")

        # Snap to the instrument's price increment (banker's rounding)
        return v.quantize(self.price_increment, rounding=ROUND_HALF_EVEN)

    def snap_qty(self, value: DecimalLike) -> Decimal:
        """Return $value snapped to $qty_increment as an exact Decimal.

        Accepts float safely by converting via `as_decimal` (which uses str(...) for non-Decimal),
        then quantizes to $qty_increment using banker’s rounding (ROUND_HALF_EVEN).

        Args:
            value: Quantity to normalize (Decimal-like scalar).

        Returns:
            Decimal: Quantity snapped to a multiple of $qty_increment.

        Raises:
            ValueError: If $value is not finite.
        """
        # Convert safely; avoid binary float artifacts by using str(...) for non-Decimal
        v = as_decimal(value)

        # Raise: input must be finite
        if not v.is_finite():
            raise ValueError(f"Cannot call `snap_qty` because $value ('{v}') is not finite")

        # Snap to the instrument's quantity increment (banker's rounding)
        return v.quantize(self.qty_increment, rounding=ROUND_HALF_EVEN)

    # endregion

    # region Special methods

    def __str__(self) -> str:
        """Return a concise string representation of the instrument.

        Returns:
            str: The instrument in format "<name>@<exchange>" (e.g., "EURUSD@FOREX").
        """
        return f"{self.name}@{self.exchange}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, exchange={self.exchange}, asset_class={self.asset_class.name}, price_increment={self.price_increment}, qty_increment={self.qty_increment}, contract_size={self.contract_size}, contract_unit={self.contract_unit}, quote_currency={self.quote_currency.code}, settlement_currency={self.settlement_currency.code})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Instrument):
            return False
        return self.name == other.name and self.exchange == other.exchange and self.asset_class == other.asset_class and self.price_increment == other.price_increment and self.qty_increment == other.qty_increment and self.contract_size == other.contract_size and self.contract_unit == other.contract_unit and self.quote_currency == other.quote_currency and self.settlement_currency == other.settlement_currency

    def __hash__(self) -> int:
        """Return hash value for the instrument.

        This allows Instrument objects to be used as dictionary keys.

        Returns:
            int: Hash value based on all attributes.
        """
        return hash(
            (
                self.name,
                self.exchange,
                self.asset_class.name,
                self.price_increment,
                self.qty_increment,
                self.contract_size,
                self.contract_unit,
                self.quote_currency.code,
                self.settlement_currency.code,
            ),
        )

    # endregion
