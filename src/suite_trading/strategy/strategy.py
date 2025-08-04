from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Set, Callable
from suite_trading.domain.event import Event
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.broker import Broker

if TYPE_CHECKING:
    from suite_trading.platform.engine.trading_engine import TradingEngine


class Strategy(ABC):
    # region Initialize and name strategy

    def __init__(self):
        """Initialize a new strategy.

        The strategy's unique name is automatically determined from the class name.
        """
        self._trading_engine = None

        self._subscribed_bar_types = set()  # Track subscribed bar types

        # Track active event feeds by reference name
        self._active_event_feeds: Set[str] = set()

    # endregion

    # region On start / stop callbacks

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

        Automatically unsubscribes from all bar subscriptions and stops all event feeds.
        """
        # Unsubscribe from all bar topics
        for bar_type in list(self._subscribed_bar_types):
            self.unsubscribe_from_live_bars(bar_type)

        # Stop all active event feeds
        event_feeds_copy = self._active_event_feeds.copy()
        for name in event_feeds_copy:
            try:
                self.remove_event_feed(name)
            except Exception as e:
                # Log error but continue cleanup
                print(f"Error stopping event feed '{name}': {e}")

    # endregion

    # region Handling market data

    def add_event_feed(self, name: str, event_type: type, parameters: dict, callback: Callable, provider_ref: str) -> None:
        """Add an event feed to start receiving events for the specified parameters.

        The strategy will receive events through the provided callback function.
        Events are delivered in chronological order across all active feeds.

        Args:
            name: Unique name for this feed within the strategy.
            event_type: Type of events to receive (e.g., NewBarEvent).
            parameters: Dictionary with event-specific parameters.
            callback: Function to call when events are received.
            provider_ref: Reference name of the provider to use for this feed.

        Raises:
            ValueError: If name is already in use.
            RuntimeError: If trading engine is not set.
            UnsupportedEventTypeError: If provider doesn't support the event type.
            UnsupportedConfigurationError: If provider doesn't support the configuration.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `add_event_feed` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        if name in self._active_event_feeds:
            raise ValueError(f"Event feed with $name '{name}' already exists. Choose a different name.")

        # Implementation: TradingEngine will:
        # 1. Validate name is unique for this strategy
        # 2. Find provider by provider_ref and validate it supports the event type and configuration
        # 3. Create EventFeed from the specified provider
        # 4. Register feed with strategy for event delivery using name and callback
        # 5. Start the feed (historical + live if requested in parameters)
        self._trading_engine.add_event_feed_for_strategy(self, name, event_type, parameters, callback, provider_ref)

        # Track the active feed
        self._active_event_feeds.add(name)

    def remove_event_feed(self, name: str) -> None:
        """Remove an event feed to stop receiving events for the specified name.

        Args:
            name: Name of the feed to stop.

        Raises:
            ValueError: If name is not found.
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `remove_event_feed` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        if name not in self._active_event_feeds:
            raise ValueError(f"No event feed with $name '{name}' is active. Cannot stop non-existent feed.")

        # Implementation: TradingEngine will:
        # 1. Find the EventFeed by name for this strategy
        # 2. Stop the feed gracefully
        # 3. Clean up resources and unregister from strategy
        self._trading_engine.remove_event_feed_for_strategy(self, name)

        # Remove from tracked feeds
        self._active_event_feeds.discard(name)

    # endregion

    # region Handle events

    # Made abstract to prevent silent failures - ensures all strategies implement event handling
    @abstractmethod
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

    # region Submit orders

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

    # region Internal and helper methods

    def _set_trading_engine(self, trading_engine: "TradingEngine"):
        """Set the trading engine reference.

        This method is called by the TradingEngine when the strategy is added to it.
        It is not expected to be called directly by subclasses.

        Args:
            trading_engine (TradingEngine): The trading engine instance.
        """
        self._trading_engine = trading_engine

    # endregion
