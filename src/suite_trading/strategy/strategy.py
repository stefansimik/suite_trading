from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Callable
from suite_trading.domain.event import Event
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.broker import Broker

if TYPE_CHECKING:
    from suite_trading.platform.engine.trading_engine import TradingEngine


class Strategy(ABC):
    # region Lifecycle

    def __init__(self):
        """Initialize a new strategy."""
        self._trading_engine = None

    def on_start(self):
        """Called when the strategy is started.

        This method should be overridden by subclasses to implement
        initialization logic when the strategy starts.
        """
        pass

    def on_stop(self):
        """Called when the strategy is stopped.

        This method should be overridden by subclasses to implement
        cleanup logic when the strategy stops.

        Note: All infrastructure cleanup (event feeds, subscriptions) is handled
        automatically by TradingEngine. Only clean up strategy-specific resources here.
        """
        # All infrastructure cleanup now handled externally
        # Override this method to add strategy-specific cleanup only
        pass

    # endregion

    # region Event delivery

    def request_event_delivery(
        self,
        name: str,
        event_type: type,
        parameters: dict,
        callback: Callable,
        provider_ref: str,
    ) -> None:
        """Request event delivery for the specified parameters.

        Sets up an event delivery mechanism that will call your callback function when events
        become available. Events may arrive immediately (historical), over time (live), or may be
        finite (historical series) or effectively unbounded (live feeds).

        Args:
            name: Unique name for this delivery request within the strategy.
            event_type: Type of events to receive (e.g., NewBarEvent).
            parameters: Dictionary with event-specific parameters.
            callback: Function to call when events are received.
            provider_ref: Reference name of the provider to use for this request.

        Raises:
            ValueError: If $name is already in use for this strategy.
            RuntimeError: If $trading_engine is None.
            UnsupportedEventTypeError: If provider doesn't support the $event_type.
            UnsupportedConfigurationError: If provider doesn't support the configuration.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `request_event_delivery` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Delegate to TradingEngine
        self._trading_engine.request_event_delivery_for_strategy(self, name, event_type, parameters, callback, provider_ref)

    def cancel_event_delivery(self, name: str) -> None:
        """Cancel an event delivery request by name.

        Safe to call even if the delivery has already completed naturally (e.g., historical data).

        Args:
            name: Name of the delivery request to cancel.

        Raises:
            ValueError: If $name is not found for this strategy.
            RuntimeError: If $trading_engine is None.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `cancel_event_delivery` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Delegate to TradingEngine - no local tracking
        self._trading_engine.cancel_event_delivery_for_strategy(self, name)

    @abstractmethod  # Made abstract to prevent silent failures - ensures all strategies implement event handling
    def on_event(self, event: Event):
        """Universal callback receiving complete event wrapper.

        This method receives the full event context including:
        - dt_received (when event entered our system)
        - dt_event (official event timestamp)
        - Complete event metadata

        This is the single central event handling method that must be implemented
        by all strategy subclasses to handle all types of events.

        Args:
            event (Event): The complete event wrapper (NewBarEvent, NewTradeTickEvent, etc.)
        """
        pass

    # endregion

    # region Orders

    def submit_order(self, order: Order, broker: Broker) -> None:
        """Submit an order for execution.

        Args:
            order (Order): The order to submit for execution.
            broker (Broker): The broker to submit the order to.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `submit_order` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.submit_order(order, broker)

    def cancel_order(self, order: Order, broker: Broker) -> None:
        """Cancel an existing order.

        Args:
            order (Order): The order to cancel.
            broker (Broker): The broker to cancel the order with.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `cancel_order` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.cancel_order(order, broker)

    def modify_order(self, order: Order, broker: Broker) -> None:
        """Modify an existing order.

        Args:
            order (Order): The order to modify with updated parameters.
            broker (Broker): The broker to modify the order with.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `modify_order` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.modify_order(order, broker)

    def get_active_orders(self, broker: Broker) -> List[Order]:
        """Get all currently active orders.

        Args:
            broker (Broker): The broker to get active orders from.

        Returns:
            List[Order]: List of all active orders for the specified broker.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `get_active_orders` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        return self._trading_engine.get_active_orders(broker)

    # endregion

    # region Internal

    def _set_trading_engine(self, trading_engine: "TradingEngine"):
        """Set the trading engine reference.

        This method is called by the TradingEngine when the strategy is added to it.
        It is not expected to be called directly by subclasses.

        Args:
            trading_engine (TradingEngine): The trading engine instance.
        """
        self._trading_engine = trading_engine

    # endregion
