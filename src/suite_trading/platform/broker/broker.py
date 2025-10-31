"""Broker protocol definition."""

from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING, Callable

from suite_trading.domain.account_info import AccountInfo
from suite_trading.domain.order.orders import Order
from suite_trading.domain.position import Position

if TYPE_CHECKING:
    from suite_trading.domain.order.execution import Execution
    from suite_trading.domain.instrument import Instrument


@runtime_checkable
class Broker(Protocol):
    """Protocol for brokers.

    This protocol defines the interface that brokers must implement
    to handle core brokerage operations including:
    - Connection management (connect, disconnect, status checking)
    - Order management (submitting, canceling, modifying, and retrieving orders)
    - Position tracking (retrieving current positions)

    Brokers serve as the bridge between trading strategies and
    actual broker/exchange systems, handling essential trading operations.
    """

    # region Connection

    def connect(self) -> None:
        """Establish connection to the broker.

        This method initializes the connection to the broker's API or trading system.
        For live brokers, this typically involves authentication and session setup.
        For `SimulatedBroker`, this is a no-op that always succeeds.

        Raises:
            ConnectionError: If connection cannot be established due to network issues,
                authentication failure, or broker system unavailability.
        """
        ...

    def disconnect(self) -> None:
        """Close broker connection.

        Should handle cases where connection is already closed gracefully.
        """
        ...

    def is_connected(self) -> bool:
        """Check connection status.

        Returns:
            bool: True if connected to broker, False otherwise.
        """
        ...

    # endregion

    # region Callbacks

    def set_callbacks(
        self,
        on_execution: Callable[[Execution], None],
        on_order_updated: Callable[[Order], None],
    ) -> None:
        """Each broker has to report changes in orders into TradingEngine

        The Broker must invoke:
         - `on_execution` callback, when a fill/partial-fill occurs
         - `on_order_updated` callback, when an order changes state

         When both happen for the same broker event, call `on_execution` first, then `on_order_updated`.
        """
        ...

    # endregion

    # region Orders

    def submit_order(self, order: Order) -> None:
        """Submit $order for execution.

        Args:
            order (Order): The order to submit for execution.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order is invalid or cannot be submitted.
        """
        ...

    def cancel_order(self, order: Order) -> None:
        """Cancel an existing $order.

        Args:
            order (Order): The Order to cancel.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If $order cannot be cancelled (e.g., already filled or not found).
        """
        ...

    def modify_order(self, order: Order) -> None:
        """Modify an existing order in place.

        Args:
            order (Order): The order carrying updated fields (e.g., limit price, quantity).

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If the order cannot be modified (e.g., already filled or not found).
            NotSupportedError: If the broker does not support order modification.
        """
        ...

    def list_active_orders(self) -> list[Order]:
        """Get all currently active orders.

        Active orders include all orders that are not in a terminal state
        (i.e., not Filled, Cancelled, or Rejected).

        Returns:
            List[Order]: List of all active orders for this broker.

        Raises:
            ConnectionError: If not connected to broker.
        """
        ...

    # endregion

    # region Positions

    def list_open_positions(self) -> list[Position]:
        """Return currently open positions.

        Returns:
            List[Position]: All open positions known to this Broker.

        Raises:
            ConnectionError: If not connected (for live brokers).
            NotSupportedError: If positions are not supported.
        """
        ...

    def get_position(self, instrument: Instrument) -> Position | None:
        """Retrieve the current Position for $instrument, or None if flat.

        Args:
            instrument: Instrument to look up.

        Returns:
            Position | None: Current Position for $instrument, or None if no open exposure.
        """
        ...

    # endregion

    # region Account

    def get_account_info(self) -> AccountInfo:
        """Return current account information (balances, margins, etc.).

        Returns:
            AccountInfo: Snapshot of account state.

        Raises:
            ConnectionError: If not connected (for live brokers).
            NotSupportedError: If accounts are not supported.
        """
        ...

    # endregion
