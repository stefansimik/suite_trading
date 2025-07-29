from typing import TYPE_CHECKING, List, Sequence, Set, Tuple, Any
from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.market_data.market_data_provider import MarketDataProvider

if TYPE_CHECKING:
    from suite_trading.platform.engine.trading_engine import TradingEngine


class Strategy:
    # region Initialization

    def __init__(self, name: str):
        """Initialize a new strategy.

        Args:
            name (str): The unique name of the strategy.

        Raises:
            ValueError: If the strategy name has empty characters at the start or end.
        """
        # Validate that the strategy name doesn't have empty characters at the start and end
        if name != name.strip():
            raise ValueError(f"$name cannot have empty characters at the start or end, but provided value is: '{name}'")

        self.name = name
        self._trading_engine = None

        self._subscribed_bar_types = set()  # Track subscribed bar types

        # NEW: Track subscriptions for cleanup - keep original parameters
        self._active_subscriptions: Set[Tuple[type, frozenset, Any]] = set()

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

    # region Strategy Lifecycle

    def _set_trading_engine(self, trading_engine: "TradingEngine"):
        """Set the trading engine reference.

        This method is called by the TradingEngine when the strategy is added to it.
        It is not expected to be called directly by subclasses.

        Args:
            trading_engine (TradingEngine): The trading engine instance.
        """
        self._trading_engine = trading_engine

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

    # -----------------------------------------------
    # SUBSCRIBE TO DATA
    # -----------------------------------------------

    # -----------------------------------------------
    # MARKET DATA REQUESTS
    # -----------------------------------------------

    # endregion

    # region Market Data Request Methods

    # NEW: Generic event-based market data methods
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
                f"Cannot call `get_historical_events` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                f"Cannot call `stream_historical_events` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                f"Cannot call `start_live_stream` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                f"Cannot call `start_live_stream_with_history` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                f"Cannot call `stop_live_stream` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Remove from tracked subscriptions - use hashable key
        details_key = self._make_parameters_key(parameters)
        self._active_subscriptions.discard((event_type, details_key, provider))

        self._trading_engine.stop_live_stream(event_type, parameters, provider, self)

    # endregion

    # region Data Handler Methods

    def on_event(self, event: Event):
        """Universal callback receiving complete event wrapper.

        This method receives the full event context including:
        - dt_received (when event entered our system)
        - dt_event (official event timestamp)
        - Complete event metadata

        Override this method when you need access to event metadata.
        The default implementation routes events to specific callbacks.

        Args:
            event (Event): The complete event wrapper (NewBarEvent, NewTradeTickEvent, etc.)
        """
        # Default implementation routes to specific handlers
        self._distribute_event_to_specific_callbacks(event)

    def _distribute_event_to_specific_callbacks(self, event: Event):
        """Internal routing method to distribute events to specific callbacks.

        This method extracts the pure data objects from event wrappers and
        calls the appropriate specific callback methods (on_bar, on_trade_tick, etc.).

        Args:
            event (Event): The event wrapper to route to specific callbacks.
        """
        if isinstance(event, NewBarEvent):
            self.on_bar(event.bar, event.is_historical)  # Extract bar and historical context from NewBarEvent
        # Add other event types as needed
        else:
            # Handle unknown event types
            self.on_unknown_event(event)

    def on_bar(self, bar: Bar, is_historical: bool):
        """Called when a new bar is received.

        This method should be overridden by subclasses to implement
        strategy logic for processing bar data.

        Args:
            bar (Bar): The bar data received.
            is_historical (bool): Whether this bar data is historical or live.
        """
        pass

    def on_historical_bars_series(self, bars: Sequence[Bar]):
        """Called when a series of historical bars is received.

        This method is called when requesting historical bar data series,
        typically from methods like get_historical_bars_series(). All bars
        in the series are historical data.

        This method should be overridden by subclasses to implement
        strategy logic for processing historical bar series data.

        Args:
            bars (Sequence[Bar]): The sequence of historical bar data received.
        """
        pass

    def on_unknown_event(self, event: Event) -> None:
        """
        Handle unknown event types. Override for custom event handling.

        Args:
            event: Unknown event type received
        """
        pass

    # endregion

    # region Order Management Methods

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
                f"Cannot call `submit_order` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                f"Cannot call `cancel_order` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                f"Cannot call `modify_order` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                f"Cannot call `get_active_orders` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        return self._trading_engine.get_active_orders(broker)

    # endregion
