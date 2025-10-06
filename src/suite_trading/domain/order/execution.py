from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Union, Optional

# TYPE_CHECKING lets us use Order for type hints without importing it at runtime.
# This avoids circular imports since Order also needs to reference Execution.
if TYPE_CHECKING:
    from suite_trading.domain.order.orders import Order

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.utils.id_generator import get_next_id


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
        id (str): Unique identifier for this execution.
        commission (Decimal): Commission/fees charged for this execution.

    Properties:
        instrument (Instrument): The financial instrument that was traded (delegates to order.instrument).
        side (OrderSide): Whether this was a BUY or SELL execution (delegates to order.side).
        gross_value (Decimal): The gross value of this execution (quantity * price).
        net_value (Decimal): The net value of this execution (gross value - commission).
        is_buy (bool): True if this is a buy execution.
        is_sell (bool): True if this is a sell execution.
    """

    def __init__(
        self,
        order: Order,
        quantity: Union[Decimal, str, float],
        price: Union[Decimal, str, float],
        timestamp: datetime,
        id: Optional[str] = None,
        commission: Union[Decimal, str, float] = Decimal("0"),
    ):
        """Initialize a new execution.

        Args:
            order: Reference to the parent order that was executed.
            quantity: The quantity that was executed in this fill.
            price: The price at which this execution occurred.
            timestamp: When this execution occurred.
            id: Unique identifier for this execution (auto-generated if None).
            commission: Commission/fees charged for this execution.

        Raises:
            ValueError: If execution data is invalid.
        """
        # Store order and timestamp
        self._order = order
        self._timestamp = timestamp

        # Generate ID if not provided
        self._id = id if id is not None else get_next_id()

        # Normalize to instrument grid for precise financial calculations
        self._quantity = self.instrument.snap_quantity(quantity)
        self._price = self.instrument.snap_price(price)
        self._commission = self._convert_to_decimal(commission)

        # Explicit validation
        self._validate()

    @staticmethod
    def _convert_to_decimal(value) -> Decimal:
        """Convert int/float/double to Decimal for precise financial calculations.

        Args:
            value: The value to convert (int, float, or Decimal).

        Returns:
            Decimal: The converted value.
        """
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    @property
    def order(self) -> Order:
        """Get the parent order."""
        return self._order

    @property
    def quantity(self) -> Decimal:
        """Get the executed quantity."""
        return self._quantity

    @property
    def price(self) -> Decimal:
        """Get the execution price."""
        return self._price

    @property
    def timestamp(self) -> datetime:
        """Get the execution timestamp."""
        return self._timestamp

    @property
    def id(self) -> str:
        """Get the execution ID."""
        return self._id

    @property
    def commission(self) -> Decimal:
        """Get the commission."""
        return self._commission

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
    def gross_value(self) -> Decimal:
        """Calculate the gross value of this execution (quantity * price).

        Returns:
            Decimal: The gross value before commissions.
        """
        return self.quantity * self.price

    @property
    def net_value(self) -> Decimal:
        """Calculate the net value of this execution (gross value - commission).

        Returns:
            Decimal: The net value after commissions.
        """
        return self.gross_value - self.commission

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

    def _validate(self) -> None:
        """Validate the execution data.

        Raises:
            ValueError: If execution data is invalid.
        """
        # Validate quantity
        if self._quantity <= 0:
            raise ValueError(f"$quantity must be positive, but provided value is: {self._quantity}")

        # Validate price
        if self._price <= 0:
            raise ValueError(f"$price must be positive, but provided value is: {self._price}")

        # Validate commission (can be 0 but not negative)
        if self._commission < 0:
            raise ValueError(f"$commission cannot be negative, but provided value is: {self._commission}")

        # Note: instrument and side consistency is guaranteed by properties that delegate to order

        # Validate that execution quantity doesn't exceed unfilled quantity
        if self._quantity > self._order.unfilled_quantity:
            raise ValueError(f"Execution $quantity ({self._quantity}) cannot exceed order unfilled quantity ({self._order.unfilled_quantity})")

    def __repr__(self) -> str:
        """Return a string representation of the execution.

        Returns:
            str: String representation of the execution.
        """
        return f"{self.__class__.__name__}(id={self.id}, order_id={self.order.id}, instrument={self.instrument}, side={self.side}, quantity={self.quantity}, price={self.price}, timestamp={self.timestamp})"

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
