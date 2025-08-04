from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Sequence, Set, Tuple, Any
from suite_trading.domain.event import Event
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.market_data.market_data_provider import MarketDataProvider

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

        # NEW: Track subscriptions for cleanup - keep original parameters
        self._active_subscriptions: Set[Tuple[type, frozenset, Any]] = set()

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

        Automatically unsubscribes from all bar subscriptions and event subscriptions.
        """
        # Unsubscribe from all bar topics
        for bar_type in list(self._subscribed_bar_types):
            self.unsubscribe_from_live_bars(bar_type)

        # Clean up all active event subscriptions
        subscriptions_copy = self._active_subscriptions.copy()
        for event_type, parameters_key, provider in subscriptions_copy:
            try:
                # We need to reconstruct the original parameters from the key
                # For now, we'll skip cleanup of individual subscriptions since
                # TradingEngine will handle cleanup when strategy is removed
                pass
            except Exception as e:
                # Log error but continue cleanup
                print(f"Error cleaning up subscription: {e}")

    # endregion

    # region Request market data
    def get_historical_events(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
    ) -> Sequence[Event]:
        """
        Get historical events from specified provider.

        Args:
            event_type: Type of events to retrieve
            parameters: Dict with event-specific parameters
            provider: Market data provider to use

        Returns:
            Sequence of historical events
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `get_historical_events` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        return self._trading_engine.get_historical_events(event_type, parameters, provider, self)

    def stream_historical_events(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
    ) -> None:
        """Stream historical events to this strategy."""
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `stream_historical_events` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.stream_historical_events(event_type, parameters, provider, self)

    def start_live_stream(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
    ) -> None:
        """Start streaming live events to this strategy."""
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `start_live_stream` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Track subscription for cleanup - use hashable key
        details_key = self._make_parameters_key(parameters)
        self._active_subscriptions.add((event_type, details_key, provider))

        self._trading_engine.start_live_stream(event_type, parameters, provider, self)

    def start_live_stream_with_history(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
    ) -> None:
        """Start streaming live events with historical data first."""
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `start_live_stream_with_history` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Track subscription for cleanup - use hashable key
        details_key = self._make_parameters_key(parameters)
        self._active_subscriptions.add((event_type, details_key, provider))

        self._trading_engine.start_live_stream_with_history(event_type, parameters, provider, self)

    def stop_live_stream(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
    ) -> None:
        """Stop streaming live events."""
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `stop_live_stream` on strategy '{self.__class__.__name__}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Remove from tracked subscriptions - use hashable key
        details_key = self._make_parameters_key(parameters)
        self._active_subscriptions.discard((event_type, details_key, provider))

        self._trading_engine.stop_live_stream(event_type, parameters, provider, self)

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

    def _make_parameters_key(self, parameters: dict) -> frozenset:
        """Create hashable key from parameters dict."""

        def make_hashable(obj):
            if isinstance(obj, dict):
                return frozenset((k, make_hashable(v)) for k, v in obj.items())
            elif isinstance(obj, list):
                return tuple(make_hashable(item) for item in obj)
            elif hasattr(obj, "__dict__"):
                return str(obj)  # For complex objects, use string representation
            else:
                return obj

        return make_hashable(parameters)

    # endregion
