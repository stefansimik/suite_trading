from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

# TYPE_CHECKING lets us use Order for type hints without importing it at runtime.
# This avoids circular imports since Order also needs to reference Execution.
if TYPE_CHECKING:
    from suite_trading.domain.order.orders import Order

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.domain.monetary.money import Money
from suite_trading.utils.datetime_utils import format_dt


class Execution:
    """Represents an order execution/fill.

    An execution represents a complete or partial fill of an order. Each execution
    records the specific details of when, how much, and at what price a portion
    of an order was filled.

    Attributes:
        order (Order): Reference to the parent order that was executed.
        quantity (Decimal): The quantity that was executed in this fill.
        price (Decimal): The price at which this execution occurred.
        timestamp (datetime): When this execution occurred.
        id (str): Unique identifier for this execution ("{order_id}-{n}").
        commission (Money): Commission/fees charged for this execution.

    Properties:
        instrument (Instrument): The financial instrument that was traded (delegates to order.instrument).
        side (OrderSide): Whether this was a BUY or SELL execution (delegates to order.side).
        is_buy (bool): True if this is a buy execution.
        is_sell (bool): True if this is a sell execution.
    """

    __slots__ = ("_order", "_quantity", "_price", "_timestamp", "_commission", "_id")

    def __init__(
        self,
        order: Order,
        quantity: Decimal | str | float,
        price: Decimal | str | float,
        timestamp: datetime,
        commission: Money,
        execution_id: str,
    ) -> None:
        """Initialize a new execution.

        Args:
            order: Reference to the parent order that was executed.
            quantity: The quantity that was executed in this fill.
            price: The price at which this execution occurred.
            timestamp: When this execution occurred.
            commission: Commission/fees charged for this execution.

        Raises:
            ValueError: If execution data is invalid.
        """
        # Store order and timestamp
        self._order = order
        self._timestamp = timestamp

        # Execution identity is assigned by Order
        self._id = execution_id

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
        """Get the execution ID."""
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
            OrderSide: Whether this was a BUY or SELL execution.
        """
        return self.order.side

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy execution.

        Returns:
            bool: True if this is a buy execution.
        """
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        """Check if this is a sell execution.

        Returns:
            bool: True if this is a sell execution.
        """
        return self.side == OrderSide.SELL

    @property
    def quantity(self) -> Decimal:
        """Get the executed quantity."""
        return self._quantity

    @property
    def price(self) -> Decimal:
        """Get the execution price."""
        return self._price

    @property
    def commission(self) -> Money:
        """Get the commission as Money."""
        return self._commission

    @property
    def timestamp(self) -> datetime:
        """Get the execution timestamp."""
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
        """Validate the execution data.

        Raises:
            ValueError: If execution data is invalid.
        """
        # Check: positive execution quantity
        if self._quantity <= 0:
            raise ValueError(f"Validation failed, because $quantity ({self._quantity}) is not positive")

        # Check: ensure $quantity is snapped to Instrument step
        expected_qty = self.instrument.snap_quantity(self._quantity)
        if expected_qty != self._quantity:
            raise ValueError(f"Validation failed, because $quantity ({self._quantity}) is not snapped to Instrument step (expected {expected_qty})")

        # Check: ensure $price is snapped to Instrument tick
        expected_price = self.instrument.snap_price(self._price)
        if expected_price != self._price:
            raise ValueError(f"Validation failed, because $price ({self._price}) is not snapped to Instrument tick (expected {expected_price})")

        # Check: ensure commission is provided to avoid half-built executions
        if self._commission is None:
            raise ValueError(f"Validation failed, because $commission is None for $order_id ('{self._order.order_id}')")

        # Check: commission cannot be negative
        if self._commission.value < 0:
            raise ValueError(f"Validation failed, because $commission ({self._commission}) is negative")

        # Check: ensure execution doesn't overfill the order
        if self._quantity > self._order.unfilled_quantity:
            raise ValueError(f"Validation failed, because $quantity ({self._quantity}) exceeds order $unfilled_quantity ({self._order.unfilled_quantity})")

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(execution_id={self.id})"

    def __repr__(self) -> str:
        """Return a string representation of the execution.

        Returns:
            str: String representation of the execution.
        """
        return f"{self.__class__.__name__}(execution_id={self.id}, order_id={self.order.order_id}, instrument={self.instrument}, side={self.side}, quantity={self.quantity}, price={self.price}, timestamp={format_dt(self.timestamp)})"

    def __eq__(self, other) -> bool:
        """Check equality with another execution.

        Args:
            other: The other execution to compare with.

        Returns:
            bool: True if executions are equal.
        """
        if not isinstance(other, Execution):
            return False
        return self.id == other.id

    # endregion
