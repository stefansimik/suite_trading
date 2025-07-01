from typing import Protocol, runtime_checkable, List, Optional
from suite_trading.domain.order.order import Order
from suite_trading.domain.position import Position
from suite_trading.domain.instrument import Instrument


@runtime_checkable
class TradingProvider(Protocol):
    """Protocol for trading/execution providers.

    The @runtime_checkable decorator from Python's typing module allows you to use
    isinstance() and issubclass() checks with Protocol classes at runtime.

    This protocol defines the interface that trading providers must implement
    to handle order management, executions, and position tracking.
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
            bool: True if connected to trading provider, False otherwise.
        """
        ...

    def submit_order(self, order: Order) -> None:
        """Submit order for execution.

        Args:
            order (Order): The order to submit for execution.

        Raises:
            ConnectionError: If not connected to trading provider.
            ValueError: If order is invalid or cannot be submitted.
        """
        ...

    def cancel_order(self, order: Order) -> None:
        """Cancel an existing order.

        Args:
            order (Order): The order to cancel.

        Raises:
            ConnectionError: If not connected to trading provider.
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
            ConnectionError: If not connected to trading provider.
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
            ConnectionError: If not connected to trading provider.
        """
        ...
