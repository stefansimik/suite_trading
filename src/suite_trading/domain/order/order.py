from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderDirection, TimeInForce
from suite_trading.domain.order.order_state import OrderState, OrderAction, create_order_state_machine
from suite_trading.utils.id_generator import get_next_id
from suite_trading.utils.state_machine import StateMachine


class Order:
    """Base class for all trading orders.

    This class contains all common attributes shared across all order types.
    It is not intended to be used directly - use specific order subclasses instead.

    Properties:
        state (OrderState): Current state of the order from the internal state machine.
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderDirection,
        quantity: Decimal,
        order_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new Order.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderDirection): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            order_id (int, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        # Order identification
        self.order_id = order_id if order_id is not None else get_next_id()

        # Trading details
        self.instrument = instrument
        self.side = side
        self.quantity = quantity

        # Execution details
        self.time_in_force = time_in_force
        self.filled_quantity = Decimal("0")  # Always initialize to 0 for new orders
        self.average_fill_price = None  # Always initialize to None for new orders

        # Internal state
        self._state_machine: StateMachine = create_order_state_machine()

        # Validation
        self._validate()

    @property
    def unfilled_quantity(self) -> Decimal:
        """Calculate remaining quantity to be filled.

        Returns:
            Decimal: The quantity still to be filled.
        """
        return self.quantity - self.filled_quantity

    @property
    def is_buy(self) -> bool:
        return self.side == OrderDirection.BUY

    @property
    def is_sell(self) -> bool:
        return self.side == OrderDirection.SELL

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
        return (
            f"{self.__class__.__name__}(order_id={self.order_id}, "
            f"instrument={self.instrument}, side={self.side}, "
            f"quantity={self.quantity}, state={self.state})"
        )

    def __eq__(self, other) -> bool:
        """Check equality with another order.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if orders are equal, False otherwise.
        """
        if not isinstance(other, Order):
            return False
        return self.order_id == other.order_id


class MarketOrder(Order):
    """Market order that executes immediately at the current market price.

    Market orders do not require any price specifications and are executed
    as quickly as possible at the best available price.
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderDirection,
        quantity: Decimal,
        order_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new MarketOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderDirection): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            order_id (int, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        super().__init__(instrument, side, quantity, order_id, time_in_force)


class LimitOrder(Order):
    """Limit order that executes only at a specified price or better.

    Limit orders require a limit_price and will only execute if the market
    price reaches the specified limit price or better.
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderDirection,
        quantity: Decimal,
        limit_price: Decimal,
        order_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new LimitOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderDirection): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            limit_price (Decimal): The limit price for the order.
            order_id (int, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        # Set limit price before calling parent constructor
        self.limit_price = limit_price

        # Call parent constructor
        super().__init__(instrument, side, quantity, order_id, time_in_force)

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
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderDirection,
        quantity: Decimal,
        stop_price: Decimal,
        order_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new StopOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderDirection): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            stop_price (Decimal): The stop price for the order.
            order_id (int, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        # Set stop price before calling parent constructor
        self.stop_price = stop_price

        # Call parent constructor
        super().__init__(instrument, side, quantity, order_id, time_in_force)

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
    """

    def __init__(
        self,
        instrument: Instrument,
        side: OrderDirection,
        quantity: Decimal,
        stop_price: Decimal,
        limit_price: Decimal,
        order_id: int = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ):
        """Initialize a new StopLimitOrder.

        Args:
            instrument (Instrument): The financial instrument to trade.
            side (OrderDirection): Whether this is a BUY or SELL order.
            quantity (Decimal): The quantity to trade.
            stop_price (Decimal): The stop price that triggers the order.
            limit_price (Decimal): The limit price for the order once triggered.
            order_id (int, optional): Unique identifier for the order. If None, generates a new ID.
            time_in_force (TimeInForce, optional): How long the order remains active. Defaults to GTC.
        """
        # Set prices before calling parent constructor
        self.stop_price = stop_price
        self.limit_price = limit_price

        # Call parent constructor
        super().__init__(instrument, side, quantity, order_id, time_in_force)

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
