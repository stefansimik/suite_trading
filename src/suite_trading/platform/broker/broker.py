"""Broker protocol definition."""

from __future__ import annotations

from typing import Callable, List, Protocol, runtime_checkable

from suite_trading.domain.account_info import AccountInfo
from suite_trading.domain.order.execution import Execution
from suite_trading.domain.order.orders import Order
from suite_trading.domain.position import Position


@runtime_checkable
class Broker(Protocol):
    """Protocol for brokers.

    The @runtime_checkable decorator from Python's typing module allows you to use
    isinstance() and issubclass() checks with Protocol classes at runtime.

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

    # region Orders

    def submit_order(self, order: Order) -> None:
        """Submit order for execution.

        Args:
            order (Order): The order to submit for execution.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order is invalid or cannot be submitted.
        """
        ...

    def cancel_order(self, order_id: str | int) -> None:
        """Cancel an existing order by its broker-assigned identifier.

        Args:
            order_id (str | int): Identifier of the order to cancel.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order cannot be cancelled (e.g., already filled or not found).
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

    def list_active_orders(self) -> List[Order]:
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

    def list_open_positions(self) -> List[Position]:
        """Return currently open positions.

        Returns:
            List[Position]: All open positions known to this Broker.

        Raises:
            ConnectionError: If not connected (for live brokers).
            NotSupportedError: If positions are not supported.
        """
        ...

    # endregion

    # region Listeners

    def add_order_updated_listener(self, listener: Callable[[Order], None]) -> None:
        """Subscribe a callback to order updates.

        Args:
            listener: Callback with signature `listener(order)` where
                - $order: Order instance that was updated.

        Returns:
            None

        Notes:
            - Duplicate subscriptions are ignored.
            - Listener is invoked for every update event for tracked orders.
        """
        ...

    def remove_order_updated_listener(self, listener: Callable[[Order], None]) -> None:
        """Unsubscribe a previously registered order-updated listener.

        Args:
            listener: The same callback object that was passed to
                `add_order_updated_listener`.

        Returns:
            None

        Notes:
            - No-op if the listener is not registered.
        """
        ...

    def add_execution_listener(self, listener: Callable[[Execution], None]) -> None:
        """Subscribe a callback to execution events (fills).

        Args:
            listener: Callback with signature `listener(execution)` where
                - $execution: Execution details (price, quantity, fees, at).

        Returns:
            None

        Notes:
            - Duplicate subscriptions are ignored.
            - Listener is invoked for each execution event (including partial fills).
        """
        ...

    def remove_execution_listener(self, listener: Callable[[Execution], None]) -> None:
        """Unsubscribe a previously registered execution listener.

        Args:
            listener: The same callback object that was passed to `add_execution_listener`.

        Returns:
            None

        Notes:
            - No-op if the listener is not registered.
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
