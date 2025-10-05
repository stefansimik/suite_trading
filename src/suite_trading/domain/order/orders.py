from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.execution import Execution
from suite_trading.domain.order.order_enums import OrderSide, TimeInForce, OrderTriggerType, TradeDirection
from suite_trading.domain.order.order_state import OrderState, OrderAction, create_order_state_machine
from suite_trading.utils.id_generator import get_next_id
from suite_trading.utils.state_machine import StateMachine, State


class Order:
    """Base class for all trading orders.

    This class contains all common attributes shared across all order types.
    It is not intended to be used directly - use specific order subclasses instead.

    Attributes:
        executions (List[Execution]): List of executions for this order, in chronological order.

    Properties:
        id (str): Unique identifier for the order (read-only).
        instrument (Instrument): The financial instrument to trade (read-only).
        side (OrderSide): Whether this is a BUY or SELL order (read-only).
        quantity (Decimal): The quantity to trade (read-only).
        trade_direction (TradeDirection): whether the trade is entry or exit trade (read-only).
        trade_id (int): Unique identifier for the trade (read-only).
        time_in_force (TimeInForce): How long the order remains active (read-only).
        state (OrderState): Current state of the order from the internal state machine.
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderSide,
        quantity: Decimal,
        trade_direction: TradeDirection,
        id: Optional[str] = None,
        trade_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new Order.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            trade_direction (TradeDirection): whether the trade is entry or exit trade
            id (str, optional): Unique identifier for the order. If None, generates a new ID.
            trade_id (int, optional): Unique identifier for the trade. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        # Order identification (private attributes with public properties)
        self._id = str(id) if id is not None else str(get_next_id())
        self._trade_id = trade_id if trade_id is not None else get_next_id()

        # Trading details (private attributes with public properties)
        self._instrument = instrument
        self._side = side
        self._quantity = instrument.snap_quantity(quantity)
        self._trade_direction = trade_direction

        # Execution details (private attributes with public properties)
        self._time_in_force = time_in_force

        # Mutable execution tracking attributes
        self.filled_quantity = Decimal("0")  # Always initialize to 0 for new orders
        self.average_fill_price = None  # Always initialize to None for new orders
        self.executions: List[Execution] = []  # List of executions in chronological order
        self.trigger_order_ids: List[(OrderTriggerType, str)] = []

        # Internal state
        self._state_machine: StateMachine = create_order_state_machine()

        # Validation
        self._validate()

    @property
    def id(self) -> str:
        """Get the unique identifier for the order.

        Returns:
            str: The order ID.
        """
        return self._id

    @property
    def trade_id(self) -> str:
        """Get the unique identifier for the trade.

        Returns:
            str: The trade ID.
        """
        return self._trade_id

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
    def trade_direction(self) -> TradeDirection:
        """Get the trade direction (ENTRY or EXIT).
        Returns:
            TradeDirection: The trade direction.
        """
        return self._trade_direction

    @property
    def quantity(self) -> Decimal:
        """Get the quantity to trade.

        Returns:
            Decimal: The order quantity.
        """
        return self._quantity

    @property
    def time_in_force(self) -> TimeInForce:
        """Get how long the order remains active.

        Returns:
            TimeInForce: The time in force setting.
        """
        return self._time_in_force

    @property
    def unfilled_quantity(self) -> Decimal:
        """Calculate remaining quantity to be filled.

        Returns:
            Decimal: The quantity still to be filled.
        """
        return self.quantity - self.filled_quantity

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

    def add_execution(self, execution: Execution) -> None:
        """Add an execution to this order.

        Executions are added in chronological order as they happen.

        Args:
            execution (Execution): The execution to add to this order.

        Raises:
            ValueError: If the execution is not for this order.
        """
        if execution.order != self:
            raise ValueError(f"Execution order with $order_id = '{execution.order.id}' does not match this order with $id = '{self.id}'")

        self.executions.append(execution)

    def add_trigger_order(self, trigger_type: OrderTriggerType, order_id: str) -> None:
        """ Add an order_id to be activated or canceled on filling the order.
        Args:
        :param trigger_type: if the order shall be activated or canceled.
        :param order_id: the unique identifier for the order.
        Raises:
            ValueError: If the order_id already exists.
        """
        for (k, v) in self.trigger_order_ids:
            if k == trigger_type and v == order_id:
                raise ValueError(f"Cannot add order_id {order_id} twice")
        self.trigger_order_ids.append( (trigger_type,order_id) )

    def get_trigger_orders(self, trigger_type: OrderTriggerType) -> List[str]:
        order_ids: List[str] = []
        for (k,v) in self.trigger_order_ids:
            if k == trigger_type:
                order_ids.append(v)
        return order_ids

    def remove_trigger_order(self, order_id: str):
        order_ids = []
        for (k, v) in self.trigger_order_ids:
            if v == order_id:
                self.trigger_order_ids.remove((k, v))

    @property
    def state(self) -> OrderState:
        """Get the current state of the order from the state machine.

        Returns:
            OrderState: The current state of the order.
        """
        return self._state_machine.current_state

    def change_state(self, action: OrderAction) -> None:
        """Change order state based on action.

        Args:
            action (OrderAction): The action to perform on the order.

        Raises:
            ValueError: If the state change is not valid for the current state.
        """
        # Execute action on the state machine - state is now managed by the property
        self._state_machine.execute_action(action)

    def _validate(self) -> None:
        """Validate the order data.

        Raises:
            ValueError: If order data is invalid.
        """
        # Validate quantity
        if self.quantity <= 0:
            raise ValueError(f"$quantity must be positive, but provided value is: {self.quantity}")

        # Validate filled_quantity
        if self.filled_quantity < 0:
            raise ValueError(f"$filled_quantity cannot be negative, but provided value is: {self.filled_quantity}")

        if self.filled_quantity > self.quantity:
            raise ValueError(f"$filled_quantity ({self.filled_quantity}) cannot exceed $quantity ({self.quantity})")

    def __repr__(self) -> str:
        """Return a string representation of the order.

        Returns:
            str: String representation of the order.
        """
        return f"{self.__class__.__name__}(id={self.id}({self.trade_id}), instrument={self.instrument}, side={self.side}, quantity={self.quantity}, state={self.state}, direction={self.trade_direction})"

    def __eq__(self, other) -> bool:
        """Check equality with another order.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if orders are equal, False otherwise.
        """
        if not isinstance(other, Order):
            return False
        return self.id == other.id

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
        trade_direction: TradeDirection,
        id: Optional[str] = None,
        trade_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new MarketOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            trade_direction (TradeDirection): whether the trade is entry or exit trade
            id (str, optional): Unique identifier for the order. If None, generates a new ID.
            trade_id (int, optional): Unique identifier for the trade. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        super().__init__(instrument, side, quantity, trade_direction, id, trade_id, time_in_force)


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
        trade_direction: TradeDirection,
        id: Optional[str] = None,
        trade_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new LimitOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            limit_price (Decimal): The limit price for the order.
            id (str, optional): Unique identifier for the order. If None, generates a new ID.
            trade_direction (TradeDirection): whether the trade is entry or exit trade
            trade_id (int, optional): Unique identifier for the trade. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        # Set limit price (private attribute with public property)
        self._limit_price = instrument.snap_price(limit_price)

        # Call parent constructor
        super().__init__(instrument, side, quantity, trade_direction, id, trade_id, time_in_force)

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
        trade_direction: TradeDirection,
        id: Optional[str] = None,
        trade_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new StopOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            stop_price (Decimal): The stop price for the order.
            trade_direction (TradeDirection): whether the trade is entry or exit trade
            id (str, optional): Unique identifier for the order. If None, generates a new ID.
            trade_id (int, optional): Unique identifier for the trade. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        # Set stop price (private attribute with public property)
        self._stop_price = instrument.snap_price(stop_price)

        # Call parent constructor
        super().__init__(instrument, side, quantity, trade_direction, id, trade_id, time_in_force)

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
        trade_direction: TradeDirection,
        id: Optional[str] = None,
        trade_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new StopLimitOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderSide): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            stop_price (Decimal): The stop price that triggers the order.
            limit_price (Decimal): The limit price for the order once triggered.
            trade_direction (TradeDirection): whether the trade is entry or exit trade
            id (str, optional): Unique identifier for the order. If None, generates a new ID.
            trade_id (int, optional): Unique identifier for the trade. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        # Set prices (private attributes with public properties)
        self._stop_price = instrument.snap_price(stop_price)
        self._limit_price = instrument.snap_price(limit_price)

        # Call parent constructor
        super().__init__(instrument, side, quantity, trade_direction, id, trade_id, time_in_force)

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
