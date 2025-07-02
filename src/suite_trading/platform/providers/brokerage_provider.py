from typing import Protocol, runtime_checkable, List, Optional
from suite_trading.domain.order.order import Order
from suite_trading.domain.position import Position
from suite_trading.domain.instrument import Instrument


@runtime_checkable
class BrokerageProvider(Protocol):
    """Protocol for brokerage service providers.

    The @runtime_checkable decorator from Python's typing module allows you to use
    isinstance() and issubclass() checks with Protocol classes at runtime.

    This protocol defines the interface that brokerage providers must implement
    to handle core brokerage operations including:
    - Connection management (connect, disconnect, status checking)
    - Order management (submitting, canceling, and retrieving orders)
    - Position tracking (retrieving current positions)

    Brokerage providers serve as the bridge between trading strategies and
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
            bool: True if connected to brokerage provider, False otherwise.
        """
        ...

    def submit_order(self, order: Order) -> None:
        """Submit order for execution.

        Args:
            order (Order): The order to submit for execution.

        Raises:
            ConnectionError: If not connected to brokerage provider.
            ValueError: If order is invalid or cannot be submitted.
        """
        ...

    def cancel_order(self, order: Order) -> None:
        """Cancel an existing order.

        Args:
            order (Order): The order to cancel.

        Raises:
            ConnectionError: If not connected to brokerage provider.
            ValueError: If order cannot be cancelled (e.g., already filled).
        """
        ...

    def get_open_orders(self, strategy: Optional[str] = None) -> List[Order]:
        """Get all open orders, optionally filtered by strategy.

        Args:
            strategy (Optional[str]): Strategy name to filter by. If None, returns all orders.

        Returns:
            List[Order]: List of open orders.

        Raises:
            ConnectionError: If not connected to brokerage provider.
        """
        ...

    def get_positions(self, strategy: Optional[str] = None, instrument: Optional[Instrument] = None) -> List[Position]:
        """Get all positions with optional filtering by strategy and/or instrument.

        Args:
            strategy (Optional[str]): Strategy name to filter by. If None, no strategy filtering.
            instrument (Optional[Instrument]): Instrument to filter by. If None, no instrument filtering.

        Returns:
            List[Position]: List of positions matching the filter criteria.

        Raises:
            ConnectionError: If not connected to brokerage provider.
        """
        ...
