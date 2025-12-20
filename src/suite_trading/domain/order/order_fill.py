from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

# TYPE_CHECKING lets us use Order for type hints without importing it at runtime.
# This avoids circular imports since Order also needs to reference OrderFill.
if TYPE_CHECKING:
    from suite_trading.domain.order.orders import Order

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.domain.monetary.money import Money
from suite_trading.utils.datetime_tools import format_dt
from suite_trading.utils.decimal_tools import DecimalLike


class OrderFill:
    """Represents a realized fill of an Order.

    A fill represents a complete or partial trade against an order. Each fill records
    the details of when, how much, and at what price a portion of the order traded.

    Attributes:
        order: Reference to the parent order that was filled.
        quantity: Filled quantity.
        price: Fill price.
        timestamp: When this fill occurred.
        id: Unique fill identifier ("{order.id}-{n}").
        commission: Commission/fees charged for this fill.

    Properties:
        instrument: The traded Instrument (delegates to $order.instrument).
        side: Whether this was a BUY or SELL fill (delegates to $order.side).
        is_buy: True if this is a buy-side fill.
        is_sell: True if this is a sell-side fill.
    """

    __slots__ = ("_order", "_quantity", "_price", "_timestamp", "_commission", "_id")

    def __init__(
        self,
        order: Order,
        quantity: DecimalLike,
        price: DecimalLike,
        timestamp: datetime,
        commission: Money,
        id: str,
    ) -> None:
        """Initialize a new fill.

        Args:
            order: Reference to the parent order that was filled.
            quantity: Filled quantity.
            price: Fill price.
            timestamp: When this fill occurred.
            commission: Commission/fees charged for this fill.

        Raises:
            ValueError: If fill data is invalid.
        """
        # Store order and timestamp
        self._order = order
        self._timestamp = timestamp

        # OrderFill identity is assigned by Order
        self._id = id

        # Normalize values
        self._quantity = self.instrument.snap_quantity(quantity)
        self._price = self.instrument.snap_price(price)

        # Commission
        self._commission = commission

        # Explicit validation
        self._validate()

    # region Properties

    @property
    def id(self) -> str:
        """Get the fill ID."""
        return self._id

    @property
    def order(self) -> Order:
        """Get the parent order."""
        return self._order

    @property
    def instrument(self) -> Instrument:
        """Get the instrument from the associated order.

        Returns:
            Instrument: The financial instrument that was traded.
        """
        return self.order.instrument

    @property
    def side(self) -> OrderSide:
        """Get the side from the associated order.

        Returns:
            OrderSide: Whether this was a BUY or SELL fill.
        """
        return self.order.side

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy-side fill.

        Returns:
            bool: True if this is a buy-side fill.
        """
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        """Check if this is a sell-side fill.

        Returns:
            bool: True if this is a sell-side fill.
        """
        return self.side == OrderSide.SELL

    @property
    def quantity(self) -> Decimal:
        """Get the filled quantity."""
        return self._quantity

    @property
    def price(self) -> Decimal:
        """Get the fill price."""
        return self._price

    @property
    def commission(self) -> Money:
        """Get the commission as Money."""
        return self._commission

    @property
    def timestamp(self) -> datetime:
        """Get the fill timestamp."""
        return self._timestamp

    @property
    def notional_value(self) -> Money:
        """Return notional Money in $quote_currency.

        Notional value explains the total theoretical value controlled by the position, not the
        margin posted. Examples:
            - BTC futures contract for 5x BTC at price $100,000 per BTC → $500,000
            - 6E futures contract for 2x contracts (125_000 EUR) at price 1.1000 -> 275_000 USD

        Returns:
            Money: Notional amount in the instrument's quote currency.
        """
        amount = self.quantity * self.instrument.contract_size * self.price
        return Money(amount, self.instrument.quote_currency)

    # endregion

    # region Utilities

    def _validate(self) -> None:
        """Validate fill invariants.

        Raises:
            ValueError: If fill data is invalid.
        """
        # Precondition: fill quantity must be positive
        if self._quantity <= 0:
            raise ValueError(f"Cannot call `OrderFill._validate` because $quantity ({self._quantity}) is not positive")

        # Precondition: quantity must be snapped
        expected_qty = self.instrument.snap_quantity(self._quantity)
        if expected_qty != self._quantity:
            raise ValueError(f"Cannot call `OrderFill._validate` because $quantity ({self._quantity}) is not snapped (expected {expected_qty})")

        # Precondition: price must be snapped
        expected_price = self.instrument.snap_price(self._price)
        if expected_price != self._price:
            raise ValueError(f"Cannot call `OrderFill._validate` because $price ({self._price}) is not snapped (expected {expected_price})")

        # Precondition: commission must be provided
        if self._commission is None:
            raise ValueError(f"Cannot call `OrderFill._validate` because $commission is None for $order.id ('{self._order.id}')")

        # Precondition: commission cannot be negative
        if self._commission.value < 0:
            raise ValueError(f"Cannot call `OrderFill._validate` because $commission ({self._commission}) is negative")

        # Precondition: a fill must not overfill the order
        if self._quantity > self._order.unfilled_quantity:
            raise ValueError(f"Cannot call `OrderFill._validate` because $quantity ({self._quantity}) exceeds order $unfilled_quantity ({self._order.unfilled_quantity})")

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id})"

    def __repr__(self) -> str:
        """Return a string representation of the fill.

        Returns:
            str: String representation of the fill.
        """
        return f"{self.__class__.__name__}(id={self.id}, order_id={self.order.id}, instrument={self.instrument}, side={self.side}, quantity={self.quantity}, price={self.price}, timestamp={format_dt(self.timestamp)})"

    def __eq__(self, other) -> bool:
        """Check equality with another fill.

        Args:
            other: The other fill to compare with.

        Returns:
            bool: True if fills are equal.
        """
        if not isinstance(other, OrderFill):
            return False
        return self.id == other.id

    # endregion
