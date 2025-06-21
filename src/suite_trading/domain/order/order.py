from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional
import random
import time

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderDirection, TimeInForce
from suite_trading.domain.order.order_state import OrderState, OrderAction, create_order_state_machine
from suite_trading.utils.state_machine import StateMachine


@dataclass
class Order:
    """Base class for all trading orders.

    This class contains all common attributes shared across all order types.
    It is not intended to be used directly - use specific order subclasses instead.

    Properties:
        state (OrderState): Current state of the order from the internal state machine.
    """

    # Trading details
    instrument: Instrument  # The financial instrument to trade
    side: OrderDirection  # Whether this is a BUY or SELL order
    quantity: Decimal  # The quantity to trade

    # Fields with defaults (must come after fields without defaults)
    order_id: int = field(default_factory=lambda: int(time.time_ns()) + random.randint(1, 999999))  # Unique random identifier for the order
    time_in_force: TimeInForce = TimeInForce.GTC  # How long the order remains active
    filled_quantity: Decimal = Decimal("0")  # How much has been filled so far
    average_fill_price: Optional[Decimal] = None  # Average price of fills
    created_time: Optional[datetime] = None  # When the order was created

    # Internal state
    _state_machine: StateMachine = field(init=False)  # Internal state machine for order lifecycle

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

    def transition(self, action: OrderAction) -> None:
        """Transition order to new state based on action.

        Args:
            action (OrderAction): The action to perform on the order.

        Raises:
            ValueError: If the transition is not valid for the current state.
        """
        # Execute action on the state machine - state is now managed by the property
        self._state_machine.execute_action(action)

    def __post_init__(self) -> None:
        """Validate the order data after initialization.

        Raises:
            ValueError: If order data is invalid.
        """
        # Initialize state machine for this order instance
        self._state_machine = create_order_state_machine()

        # Validate quantity
        if self.quantity <= 0:
            raise ValueError(f"$quantity must be positive, but provided value is: {self.quantity}")

        # Validate filled_quantity
        if self.filled_quantity < 0:
            raise ValueError(f"$filled_quantity cannot be negative, but provided value is: {self.filled_quantity}")

        if self.filled_quantity > self.quantity:
            raise ValueError(f"$filled_quantity ({self.filled_quantity}) cannot exceed $quantity ({self.quantity})")


@dataclass
class MarketOrder(Order):
    """Market order that executes immediately at the current market price.

    Market orders do not require any price specifications and are executed
    as quickly as possible at the best available price.
    """

    def __post_init__(self) -> None:
        """Initialize and validate the market order."""
        super().__post_init__()


@dataclass
class LimitOrder(Order):
    """Limit order that executes only at a specified price or better.

    Limit orders require a limit_price and will only execute if the market
    price reaches the specified limit price or better.
    """

    limit_price: Decimal = field(kw_only=True)  # The limit price for the order

    def __post_init__(self) -> None:
        """Initialize and validate the limit order."""
        super().__post_init__()

        # Validate limit_price is positive
        if self.limit_price <= 0:
            raise ValueError(f"$limit_price must be positive, but provided value is: {self.limit_price}")


@dataclass
class StopOrder(Order):
    """Stop order that becomes a market order when the stop price is reached.

    Stop orders require a stop_price and will trigger a market order
    when the market price reaches the specified stop price.
    """

    stop_price: Decimal = field(kw_only=True)  # The stop price for the order

    def __post_init__(self) -> None:
        """Initialize and validate the stop order."""
        super().__post_init__()

        # Validate stop_price is positive
        if self.stop_price <= 0:
            raise ValueError(f"$stop_price must be positive, but provided value is: {self.stop_price}")


@dataclass
class StopLimitOrder(Order):
    """Stop-limit order that becomes a limit order when the stop price is reached.

    Stop-limit orders require both a stop_price and limit_price. When the market
    price reaches the stop price, the order becomes a limit order at the limit price.
    """

    stop_price: Decimal = field(kw_only=True)  # The stop price that triggers the order
    limit_price: Decimal = field(kw_only=True)  # The limit price for the order once triggered

    def __post_init__(self) -> None:
        """Initialize and validate the stop-limit order."""
        super().__post_init__()

        # Validate both prices are positive
        if self.stop_price <= 0:
            raise ValueError(f"$stop_price must be positive, but provided value is: {self.stop_price}")

        if self.limit_price <= 0:
            raise ValueError(f"$limit_price must be positive, but provided value is: {self.limit_price}")
