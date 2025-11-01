from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

# TYPE_CHECKING lets us use Order for type hints without importing it at runtime.
# This avoids circular imports since Order also needs to reference Execution.
if TYPE_CHECKING:
    from suite_trading.domain.order.orders import Order
    from suite_trading.domain.monetary.money import Money

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.utils.datetime_utils import format_dt


# region Executions


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
        commission (Money | None): Commission/fees charged for this execution (Money if set).

    Properties:
        instrument (Instrument): The financial instrument that was traded (delegates to order.instrument).
        side (OrderSide): Whether this was a BUY or SELL execution (delegates to order.side).
        gross_value (Decimal): The gross value of this execution (quantity * price).
        net_value (Decimal): The net value of this execution (gross value - commission).
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
        commission: Money | None = None,
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

        # Derive ID as "{order_id}-{next_seq}" (1-based per-order execution index)
        # We intentionally use the current length of $order.executions so the first fill is 1.
        executions_count = len(order.executions) + 1
        self._id = f"{order.order_id}-{executions_count}"

        # Normalize to instrument grid for precise financial calculations
        self._quantity = self.instrument.snap_quantity(quantity)
        self._price = self.instrument.snap_price(price)
        # Commission is Money (or None until broker sets it)
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
    def commission(self) -> Money | None:
        """Get the commission as Money or None when not yet set."""
        return self._commission

    @commission.setter
    def commission(self, value: Money | None) -> None:
        """Set commission as Money or None.

        Args:
            value: Commission to set for this execution, or None.
        """
        # Check: commission cannot be negative when provided
        if value is not None and value.value < 0:
            raise ValueError(f"Cannot set `commission` because $commission ({value}) is negative")
        self._commission = value

    @property
    def timestamp(self) -> datetime:
        """Get the execution timestamp."""
        return self._timestamp

    @property
    def gross_value(self) -> Decimal:
        """Calculate the gross value of this execution (quantity * price).

        Returns:
            Decimal: The gross value before commissions.
        """
        return self.quantity * self.price

    @property
    def net_value(self) -> Decimal:
        """Calculate the net value = gross value minus commission.value if present.

        Returns:
            Decimal: The net value after commissions (uses $commission.value when set).
        """
        commission_value: Decimal = Decimal("0") if self._commission is None else self._commission.value
        return self.gross_value - commission_value

    # endregion

    # region Utilities

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

    def _validate(self) -> None:
        """Validate the execution data.

        Raises:
            ValueError: If execution data is invalid.
        """
        # Check: positive execution quantity
        if self._quantity <= 0:
            raise ValueError(f"Cannot call `_validate` because $quantity ({self._quantity}) is not positive")

        # Note: Do not reject negative prices here; some markets allow them (see guideline 7.1)

        # Check: commission cannot be negative (when set)
        if self._commission is not None and self._commission.value < 0:
            raise ValueError(f"Cannot call `_validate` because $commission ({self._commission}) is negative")

        # Note: instrument and side consistency is guaranteed by properties that delegate to order

        # Check: ensure execution doesn't overfill the order
        if self._quantity > self._order.unfilled_quantity:
            raise ValueError(f"Cannot call `_validate` because $quantity ({self._quantity}) exceeds order $unfilled_quantity ({self._order.unfilled_quantity})")

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


# endregion
