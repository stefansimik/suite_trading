from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.execution import Execution
from suite_trading.domain.order.order_enums import OrderSide, TimeInForce
from suite_trading.domain.order.order_state import OrderState, OrderAction, create_order_state_machine
from suite_trading.utils.id_generator import get_next_id
from suite_trading.utils.state_machine import StateMachine

if TYPE_CHECKING:
    from suite_trading.strategy.strategy import Strategy


# region Orders


class Order:
    """Base class for all trading orders.

    This class contains all common attributes shared across all order types.
    It is not intended to be used directly - use specific order subclasses instead.

    Attributes:
        executions (List[Execution]): List of executions for this order, in chronological order.

    Properties:
        order_id (str): Unique identifier for the order (read-only).
        instrument (Instrument): The financial instrument to trade (read-only).
        side (OrderSide): Whether this is a BUY or SELL order (read-only).
        quantity (Decimal): The quantity to trade (read-only).
        time_in_force (TimeInForce): How long the order remains active (read-only).
        state (OrderState): Current state of the order from the internal state machine.
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderSide,
        quantity: Decimal,
        order_id: str | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        strategy: Strategy | None = None,
    ):
        """Initialize a new Order.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            order_id (str, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
            strategy (Strategy | None, optional): Strategy that created this order, if any.
        """
        # Order identification (private attributes with public properties)
        self._order_id = str(order_id) if order_id is not None else str(get_next_id())

        # Trading details (private attributes with public properties)
        self._instrument = instrument
        self._side = side
        self._quantity = instrument.snap_quantity(quantity)

        # Execution details (private attributes with public properties)
        self._time_in_force = time_in_force

        # Reference to Strategy that created this order (may be None)
        self._strategy = strategy

        # Execution tracking (single source of truth)
        self.executions: list[Execution] = []  # Chronological by append order

        # Internal state
        self._state_machine: StateMachine = create_order_state_machine()

        # Validation
        self._validate()

    # region Properties

    @property
    def order_id(self) -> str:
        """Get the unique identifier for the order.

        Returns:
            str: The order ID.
        """
        return self._order_id

    @property
    def instrument(self) -> Instrument:
        """Get the financial instrument to trade.

        Returns:
            Instrument: The financial instrument.
        """
        return self._instrument

    @property
    def side(self) -> OrderSide:
        """Get the order side (BUY or SELL).

        Returns:
            OrderSide: The order side.
        """
        return self._side

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy order.

        Returns:
            bool: True if this is a buy order.
        """
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        """Check if this is a sell order.

        Returns:
            bool: True if this is a sell order.
        """
        return self.side == OrderSide.SELL

    @property
    def quantity(self) -> Decimal:
        """Get the quantity to trade.

        Returns:
            Decimal: The order quantity.
        """
        return self._quantity

    @property
    def filled_quantity(self) -> Decimal:
        """Total executed quantity across `executions`.

        Returns:
            Decimal: Sum of execution quantities.
        """
        total = Decimal("0")
        for e in self.executions:
            total += e.quantity
        return total

    @property
    def unfilled_quantity(self) -> Decimal:
        """Remaining unfilled quantity for this order."""
        return self.quantity - self.filled_quantity

    @property
    def is_unfilled(self) -> bool:
        """Whether no quantity has been filled yet.

        Returns:
            bool: True if $filled_quantity is 0.
        """
        return self.filled_quantity == Decimal("0")

    @property
    def is_partially_filled(self) -> bool:
        """Whether some, but not all, quantity has been filled.

        Returns:
            bool: True if 0 < $filled_quantity < $quantity.
        """
        filled = self.filled_quantity
        return Decimal("0") < filled < self.quantity

    @property
    def is_fully_filled(self) -> bool:
        """Whether the order has been completely filled.

        Returns:
            bool: True if $filled_quantity == $quantity.
        """
        return self.filled_quantity == self.quantity

    @property
    def average_fill_price(self) -> Decimal | None:
        """Weighted average price (VWAP) of executions, or None if no fills.

        Note:
            VWAP is not snapped to tick size; it may fall between ticks. Use
            presentation-layer formatting if you need display rounding.

        Returns:
            Decimal | None: VWAP of executions, or None.
        """
        filled = self.filled_quantity
        if filled == 0:
            return None

        notional = Decimal("0")
        for e in self.executions:
            notional += e.price * e.quantity

        avg_price = notional / filled
        return avg_price

    @property
    def time_in_force(self) -> TimeInForce:
        """Get how long the order remains active.

        Returns:
            TimeInForce: The time in force setting.
        """
        return self._time_in_force

    @property
    def strategy(self) -> Strategy | None:
        """Get the Strategy that created this order, if available.

        Returns:
            Optional[Strategy]: The Strategy reference or None.
        """
        return self._strategy

    @property
    def state(self) -> OrderState:
        """Get the current state of the order from the state machine.

        Returns:
            OrderState: The current state of the order.
        """
        return self._state_machine.current_state

    # endregion

    # region Main

    def add_execution(self, execution: Execution) -> None:
        """Add a new execution for this order in chronological order.

        Args:
            execution: The execution to record.

        Raises:
            ValueError: If the execution belongs to a different order, has non-positive $quantity, or would overfill the order.
        """
        # Check: execution must belong to this order
        if execution.order != self:
            raise ValueError(f"Cannot call `add_execution` because $execution.order_id ('{execution.order.order_id}') does not match this Order $order_id ('{self.order_id}')")
        # Check: positive execution quantity
        if execution.quantity <= 0:
            raise ValueError(f"Cannot call `add_execution` with non-positive $quantity ({execution.quantity}); provide a positive quantity")
        # Check: disallow overfill (quantities already snapped)
        new_filled = self.filled_quantity + execution.quantity
        if new_filled > self.quantity:
            raise ValueError(f"Cannot call `add_execution` because resulting $filled_quantity ({new_filled}) would exceed $quantity ({self.quantity})")

        self.executions.append(execution)

    def change_state(self, action: OrderAction) -> None:
        """Change order state based on action.

        Args:
            action (OrderAction): The action to perform on the order.

        Raises:
            ValueError: If the state change is not valid for the current state.
        """
        # Execute action on the state machine - state is now managed by the property
        self._state_machine.execute_action(action)

    # endregion

    # region Utilities

    def _validate(self) -> None:
        """Validate intrinsic order inputs at construction time.

        Raises:
            ValueError: If $quantity <= 0.
        """
        # Check: positive order quantity
        if self.quantity <= 0:
            raise ValueError(f"Cannot call `_validate` because $quantity ({self.quantity}) is not positive")

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(order_id={self.order_id}, instrument={self.instrument}, side={self.side}, quantity={self.quantity}, state={self.state})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(order_id={self.order_id}, instrument={self.instrument}, side={self.side}, quantity={self.quantity}, state={self.state})"

    def __eq__(self, other: object) -> bool:
        """Check equality with another order.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if orders are equal, False otherwise.
        """
        if not isinstance(other, Order):
            return False
        return self.order_id == other.order_id

    def __hash__(self) -> int:
        """Allow using Order as dictionary key and in sets.

        Hash is derived from stable `order_id` to be consistent with `__eq__`.
        """
        return hash(self.order_id)


# endregion


class MarketOrder(Order):
    """Market order that executes immediately at the current market price.

    Market orders do not require any price specifications and are executed
    as quickly as possible at the best available price.
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderSide,
        quantity: Decimal,
        order_id: str | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        strategy: Strategy | None = None,
    ):
        """Initialize a new MarketOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            order_id (str, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
            strategy (Strategy | None, optional): Strategy that created this order, if any.
        """
        super().__init__(instrument, side, quantity, order_id, time_in_force, strategy)


class LimitOrder(Order):
    """Limit order that executes only at a specified price or better.

    Limit orders require a limit_price and will only execute if the market
    price reaches the specified limit price or better.

    Properties:
        limit_price (Decimal): The limit price for the order (read-only).
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderSide,
        quantity: Decimal,
        limit_price: Decimal,
        order_id: str | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        strategy: Strategy | None = None,
    ):
        """Initialize a new LimitOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            limit_price (Decimal): The limit price for the order.
            order_id (str, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
            strategy (Strategy | None, optional): Strategy that created this order, if any.
        """
        # Set limit price (private attribute with public property)
        self._limit_price = instrument.snap_price(limit_price)

        # Call parent constructor
        super().__init__(instrument, side, quantity, order_id, time_in_force, strategy)

    @property
    def limit_price(self) -> Decimal:
        """Get the limit price for the order.

        Returns:
            Decimal: The limit price.
        """
        return self._limit_price

    def _validate(self) -> None:
        """Validate the limit order data.

        Raises:
            ValueError: If order data is invalid.
        """
        # Call parent validation first
        super()._validate()

        # Validate limit_price is positive
        if self.limit_price <= 0:
            raise ValueError(f"$limit_price must be positive, but provided value is: {self.limit_price}")


class StopOrder(Order):
    """Stop order that becomes a market order when the stop price is reached.

    Stop orders require a stop_price and will trigger a market order
    when the market price reaches the specified stop price.

    Properties:
        stop_price (Decimal): The stop price for the order (read-only).
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderSide,
        quantity: Decimal,
        stop_price: Decimal,
        order_id: str | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        strategy: Strategy | None = None,
    ):
        """Initialize a new StopOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            stop_price (Decimal): The stop price for the order.
            order_id (str, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
            strategy (Strategy | None, optional): Strategy that created this order, if any.
        """
        # Set stop price (private attribute with public property)
        self._stop_price = instrument.snap_price(stop_price)

        # Call parent constructor
        super().__init__(instrument, side, quantity, order_id, time_in_force, strategy)

    @property
    def stop_price(self) -> Decimal:
        """Get the stop price for the order.

        Returns:
            Decimal: The stop price.
        """
        return self._stop_price

    def _validate(self) -> None:
        """Validate the stop order data.

        Raises:
            ValueError: If order data is invalid.
        """
        # Call parent validation first
        super()._validate()

        # Validate stop_price is positive
        if self.stop_price <= 0:
            raise ValueError(f"$stop_price must be positive, but provided value is: {self.stop_price}")


class StopLimitOrder(Order):
    """Stop-limit order that becomes a limit order when the stop price is reached.

    Stop-limit orders require both a stop_price and limit_price. When the market
    price reaches the stop price, the order becomes a limit order at the limit price.

    Properties:
        stop_price (Decimal): The stop price that triggers the order (read-only).
        limit_price (Decimal): The limit price for the order once triggered (read-only).
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderSide,
        quantity: Decimal,
        stop_price: Decimal,
        limit_price: Decimal,
        order_id: str | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        strategy: Strategy | None = None,
    ):
        """Initialize a new StopLimitOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            stop_price (Decimal): The stop price that triggers the order.
            limit_price (Decimal): The limit price for the order once triggered.
            order_id (str, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
            strategy (Strategy | None, optional): Strategy that created this order, if any.
        """
        # Set prices (private attributes with public properties)
        self._stop_price = instrument.snap_price(stop_price)
        self._limit_price = instrument.snap_price(limit_price)

        # Call parent constructor
        super().__init__(instrument, side, quantity, order_id, time_in_force, strategy)

    @property
    def stop_price(self) -> Decimal:
        """Get the stop price that triggers the order.

        Returns:
            Decimal: The stop price.
        """
        return self._stop_price

    @property
    def limit_price(self) -> Decimal:
        """Get the limit price for the order once triggered.

        Returns:
            Decimal: The limit price.
        """
        return self._limit_price

    def _validate(self) -> None:
        """Validate the stop-limit order data.

        Raises:
            ValueError: If order data is invalid.
        """
        # Call parent validation first
        super()._validate()

        # Validate both prices are positive
        if self.stop_price <= 0:
            raise ValueError(f"$stop_price must be positive, but provided value is: {self.stop_price}")

        if self.limit_price <= 0:
            raise ValueError(f"$limit_price must be positive, but provided value is: {self.limit_price}")


# endregion
