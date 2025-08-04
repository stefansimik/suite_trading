"""Broker protocol definition."""

from typing import List, Protocol, runtime_checkable

from suite_trading.domain.order.orders import Order


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

    def connect(self) -> None:
        """Establish broker connection.

        Raises:
            ConnectionError: If connection cannot be established.
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

    def submit_order(self, order: Order) -> None:
        """Submit order for execution.

        Args:
            order (Order): The order to submit for execution.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order is invalid or cannot be submitted.
        """
        ...

    def cancel_order(self, order: Order) -> None:
        """Cancel an existing order.

        Args:
            order (Order): The order to cancel.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order cannot be cancelled (e.g., already filled).
        """
        ...

    def modify_order(self, order: Order) -> None:
        """Modify an existing order.

        Args:
            order (Order): The order to modify with updated parameters.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order cannot be modified (e.g., already filled).
        """
        ...

    def get_active_orders(self) -> List[Order]:
        """Get all currently active orders.

        Returns:
            List[Order]: List of all active orders for this broker.

        Raises:
            ConnectionError: If not connected to broker.
        """
        ...
