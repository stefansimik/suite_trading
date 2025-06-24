from datetime import datetime
from decimal import Decimal
from typing import Optional

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.utils.id_generator import get_next_id
from suite_trading.domain.order.order import Order


class Execution:
    """Represents an order execution/fill.

    An execution represents a complete or partial fill of an order. Each execution
    records the specific details of when, how much, and at what price a portion
    of an order was filled.

    Attributes:
        id (str): Unique identifier for this execution.
        order (Order): Reference to the parent order that was executed.
        quantity (Decimal): The quantity that was executed in this fill.
        price (Decimal): The price at which this execution occurred.
        timestamp (datetime): When this execution occurred.
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
        quantity: Decimal,
        price: Decimal,
        timestamp: datetime,
        id: Optional[str] = None,
        commission: Decimal = Decimal("0"),
    ):
        """Initialize a new Execution.

        Args:
            order (Order): Reference to the parent order that was executed.
            quantity (Decimal): The quantity that was executed in this fill.
            price (Decimal): The price at which this execution occurred.
            timestamp (datetime): When this execution occurred.
            id (str, optional): Unique identifier for this execution. If None, generates a new ID.
            commission (Decimal, optional): Commission/fees charged for this execution. Defaults to 0.
        """
        # Execution identification
        self.id = id if id is not None else get_next_id()

        # Order relationship
        self.order = order

        # Trading details
        self.quantity = self._convert_to_decimal(quantity)
        self.price = self._convert_to_decimal(price)

        # Execution metadata
        self.timestamp = timestamp
        self.commission = self._convert_to_decimal(commission)

        # Validation
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
        if self.quantity <= 0:
            raise ValueError(f"$quantity must be positive, but provided value is: {self.quantity}")

        # Validate price
        if self.price <= 0:
            raise ValueError(f"$price must be positive, but provided value is: {self.price}")

        # Validate commission (can be 0 but not negative)
        if self.commission < 0:
            raise ValueError(f"$commission cannot be negative, but provided value is: {self.commission}")

        # Note: instrument and side consistency is guaranteed by properties that delegate to order

        # Validate that execution quantity doesn't exceed unfilled quantity
        if self.quantity > self.order.unfilled_quantity:
            raise ValueError(f"Execution $quantity ({self.quantity}) cannot exceed order unfilled quantity ({self.order.unfilled_quantity})")

    def __repr__(self) -> str:
        """Return a string representation of the execution.

        Returns:
            str: String representation of the execution.
        """
        return (
            f"Execution(id={self.id}, "
            f"order_id={self.order.id}, instrument={self.instrument}, "
            f"side={self.side}, quantity={self.quantity}, price={self.price}, "
            f"timestamp={self.timestamp})"
        )

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
