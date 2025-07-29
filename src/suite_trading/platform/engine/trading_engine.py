import logging
from datetime import datetime
from typing import Dict, List, Sequence, Set, Tuple, Any
from collections import defaultdict
from suite_trading.strategy.base import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.topic_factory import TopicFactory
from suite_trading.platform.market_data.market_data_provider import MarketDataProvider
from suite_trading.platform.broker.broker import Broker
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.order.orders import Order
from suite_trading.domain.event import Event

logger = logging.getLogger(__name__)


class TradingEngine:
    """Simple engine for managing and running trading strategies.

    The TradingEngine coordinates strategies and provides a framework for strategy
    execution and management.

    **Architecture:**
    - **Strategies**: Implement trading logic and subscribe to events via MessageBus
    - **MessageBus**: Handles event distribution to strategies

    This simple design focuses on strategy coordination and management.
    """

    # region Initialize engine

    def __init__(self):
        """Initialize a new TradingEngine instance.

        Creates its own MessageBus instance for isolated operation.
        """
        self.strategies: list[Strategy] = []
        self._is_running: bool = False
        self.message_bus = MessageBus()

        # Market data provider management
        self._market_data_providers: Dict[str, MarketDataProvider] = {}

        # Broker management
        self._brokers: Dict[str, Broker] = {}

        # Track strategy subscriptions for demand-based publishing
        self._bar_subscriptions: dict[BarType, set[Strategy]] = {}  # Track which strategies subscribe to which bar types

        # NEW: Subscription tracking for generic events - keep original parameters
        # Key: (event_type, frozenset of parameters items) -> Set of strategies
        self._event_subscriptions: Dict[Tuple[type, frozenset], Set[Any]] = defaultdict(set)

        # Key: (provider, event_type, frozenset of parameters items) -> active stream count
        self._active_streams: Dict[Tuple[Any, type, frozenset], int] = defaultdict(int)

        # Key: strategy -> Set of (event_type, parameters_key, provider)
        self._strategy_subscriptions: Dict[Any, Set[Tuple[type, frozenset, Any]]] = defaultdict(set)

    # endregion

    # region Start and stop engine

    def start(self):
        """Start the TradingEngine and all strategies.

        This method starts all registered strategies.
        """
        self._is_running = True

        # Start strategies
        for strategy in self.strategies:
            strategy.on_start()

    def stop(self):
        """Stop the TradingEngine and all strategies.

        This method stops all registered strategies.
        """
        self._is_running = False

        # Stop strategies
        for strategy in self.strategies:
            strategy.on_stop()

    # endregion

    # region Manage strategies

    def add_strategy(self, strategy: Strategy):
        """Add a strategy to the engine.

        Args:
            strategy (Strategy): The strategy to add.

        Raises:
            ValueError: If a strategy with the same name already exists.
        """
        # Make sure each strategy has unique name
        for existing_strategy in self.strategies:
            if existing_strategy.name == strategy.name:
                raise ValueError(
                    f"$strategy cannot be added, because it does not have unique name. Strategy with $name '{strategy.name}' already exists and another one with same name cannot be added again.",
                )

        # Set the trading engine reference in the strategy
        strategy._set_trading_engine(self)
        self.strategies.append(strategy)

        # Initialize strategy subscription tracking
        self._strategy_subscriptions[strategy] = set()

    def remove_strategy(self, strategy: Strategy) -> None:
        """Remove a strategy from the engine and clean up its subscriptions.

        Args:
            strategy: The strategy to remove.

        Raises:
            ValueError: If the strategy is not found.
        """
        if strategy not in self.strategies:
            raise ValueError(f"Strategy '{strategy.name}' is not registered with this engine.")

        # Clean up all subscriptions for this strategy
        self._cleanup_strategy_subscriptions(strategy)

        # Remove from strategies list
        self.strategies.remove(strategy)

    def _cleanup_strategy_subscriptions(self, strategy: Strategy) -> None:
        """Clean up all subscriptions for a strategy when it stops."""
        if strategy not in self._strategy_subscriptions:
            return

        # Get copy of subscriptions to avoid modification during iteration
        subscriptions = self._strategy_subscriptions[strategy].copy()

        for event_type, parameters_key, provider in subscriptions:
            try:
                # We need to reconstruct the original parameters from the key
                # For cleanup, we'll directly remove from tracking without calling stop_live_stream
                # since the provider cleanup will be handled elsewhere
                self._strategy_subscriptions[strategy].discard((event_type, parameters_key, provider))

                # Clean up event subscriptions
                subscription_key = (event_type, parameters_key)
                self._event_subscriptions[subscription_key].discard(strategy)
                if not self._event_subscriptions[subscription_key]:
                    del self._event_subscriptions[subscription_key]

                # Clean up active streams
                stream_key = (provider, event_type, parameters_key)
                if stream_key in self._active_streams:
                    self._active_streams[stream_key] -= 1
                    if self._active_streams[stream_key] <= 0:
                        del self._active_streams[stream_key]

            except Exception as e:
                # Log error but continue cleanup
                logger.warning(f"Error cleaning up subscription: {e}")

        # Clean up the strategy's subscription tracking
        del self._strategy_subscriptions[strategy]

    # endregion

    # region Manage market data providers

    def add_market_data_provider(self, name: str, provider: MarketDataProvider) -> None:
        """Register a market data provider under the given name.

        Args:
            name: Name to register the provider under.
            provider: The market data provider instance to register.

        Raises:
            ValueError: If a provider with the same name already exists.
        """
        if name in self._market_data_providers:
            raise ValueError(f"Market data provider with $name '{name}' already exists. Cannot add another provider with the same name.")

        self._market_data_providers[name] = provider

    def remove_market_data_provider(self, name: str) -> None:
        """Remove a market data provider by name.

        Args:
            name: Name of the provider to remove.

        Raises:
            KeyError: If no provider with the given name exists.
        """
        if name not in self._market_data_providers:
            raise KeyError(f"No market data provider with $name '{name}' is registered. Cannot remove non-existent provider.")

        del self._market_data_providers[name]

    @property
    def market_data_providers(self) -> Dict[str, MarketDataProvider]:
        """Get all registered market data providers.

        Returns:
            Dictionary mapping provider names to provider instances.
        """
        return self._market_data_providers

    # endregion

    # region Manage brokers

    def add_broker(self, name: str, broker: Broker) -> None:
        """Register a broker under the given name.

        Args:
            name: Name to register the broker under.
            broker: The broker instance to register.

        Raises:
            ValueError: If a broker with the same name already exists.
        """
        if name in self._brokers:
            raise ValueError(f"Broker with $name '{name}' already exists. Cannot add another broker with the same name.")

        self._brokers[name] = broker

    def remove_broker(self, name: str) -> None:
        """Remove a broker by name.

        Args:
            name: Name of the broker to remove.

        Raises:
            KeyError: If no broker with the given name exists.
        """
        if name not in self._brokers:
            raise KeyError(f"No broker with $name '{name}' is registered. Cannot remove non-existent broker.")

        del self._brokers[name]

    @property
    def brokers(self) -> Dict[str, Broker]:
        """Get all registered brokers.

        Returns:
            Dictionary mapping broker names to broker instances.
        """
        return self._brokers

    # endregion

    # region Request market data

    def get_historical_events(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
        strategy: Strategy,
    ) -> Sequence[Event]:
        """
        Get historical events from specified provider.

        Args:
            event_type: Type of events to retrieve
            parameters: Dict with event-specific parameters
            provider: Market data provider to use
            strategy: Strategy making the request

        Returns:
            Sequence of historical events

        Raises:
            UnsupportedEventTypeError: If provider doesn't support the event type
        """
        return provider.get_historical_events(event_type, parameters)

    def stream_historical_events(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
        strategy: Strategy,
    ) -> None:
        """
        Stream historical events to strategy via MessageBus.

        Raises:
            UnsupportedEventTypeError: If provider doesn't support the event type
        """
        # Generate topic and subscribe strategy
        topic = self._generate_topic(event_type, parameters)
        self.message_bus.subscribe(topic, strategy.on_event)

        # Delegate to provider
        provider.stream_historical_events(event_type, parameters)

    def start_live_stream(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
        strategy: Strategy,
    ) -> None:
        """
        Start streaming live events to strategy.

        Raises:
            UnsupportedEventTypeError: If provider doesn't support the event type
        """
        # Track subscription - keep original parameters
        details_key = self._make_parameters_key(parameters)
        subscription_key = (event_type, details_key)
        stream_key = (provider, event_type, details_key)

        # Add strategy to subscribers
        self._event_subscriptions[subscription_key].add(strategy)
        self._strategy_subscriptions[strategy].add((event_type, details_key, provider))

        # Subscribe strategy to MessageBus topic
        topic = self._generate_topic(event_type, parameters)
        self.message_bus.subscribe(topic, strategy.on_event)

        # Start provider stream if this is first subscriber
        if self._active_streams[stream_key] == 0:
            provider.start_live_stream(event_type, parameters)

        self._active_streams[stream_key] += 1

    def start_live_stream_with_history(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
        strategy: Strategy,
    ) -> None:
        """
        Start streaming live events with historical data first.

        Raises:
            UnsupportedEventTypeError: If provider doesn't support the event type
        """
        # Track subscription - keep original parameters
        details_key = self._make_parameters_key(parameters)
        subscription_key = (event_type, details_key)
        stream_key = (provider, event_type, details_key)

        # Add strategy to subscribers
        self._event_subscriptions[subscription_key].add(strategy)
        self._strategy_subscriptions[strategy].add((event_type, details_key, provider))

        # Subscribe strategy to MessageBus topic
        topic = self._generate_topic(event_type, parameters)
        self.message_bus.subscribe(topic, strategy.on_event)

        # Start provider stream if this is first subscriber
        if self._active_streams[stream_key] == 0:
            provider.start_live_stream_with_history(event_type, parameters)

        self._active_streams[stream_key] += 1

    def stop_live_stream(
        self,
        event_type: type,
        parameters: dict,
        provider: MarketDataProvider,
        strategy: Strategy,
    ) -> None:
        """Stop streaming live events for strategy."""
        details_key = self._make_parameters_key(parameters)
        subscription_key = (event_type, details_key)
        stream_key = (provider, event_type, details_key)

        # Remove strategy from subscribers
        self._event_subscriptions[subscription_key].discard(strategy)
        self._strategy_subscriptions[strategy].discard((event_type, details_key, provider))

        # Unsubscribe from MessageBus
        topic = self._generate_topic(event_type, parameters)
        self.message_bus.unsubscribe(topic, strategy.on_event)

        # Stop provider stream if no more subscribers
        self._active_streams[stream_key] -= 1
        if self._active_streams[stream_key] <= 0:
            provider.stop_live_stream(event_type, parameters)
            del self._active_streams[stream_key]

        # Clean up empty subscription sets
        if not self._event_subscriptions[subscription_key]:
            del self._event_subscriptions[subscription_key]

    # endregion

    # region Helper methods

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

    def _generate_topic(self, event_type: type, parameters: dict) -> str:
        """Generate topic for event type and parameters."""
        return TopicFactory.create_topic_for_event(event_type, parameters)

    def publish_bar(self, bar: Bar, is_historical: bool = True) -> None:
        """Publish a bar to the MessageBus for distribution to subscribed strategies.

        Creates a NewBarEvent with the specified historical context and publishes it to the appropriate topic.

        Args:
            bar: The bar to publish.
            is_historical: Whether this bar data is historical or live. Defaults to True.
        """
        event = NewBarEvent(bar=bar, dt_received=datetime.now(), is_historical=is_historical)
        topic = TopicFactory.create_topic_for_bar(bar.bar_type)
        self.message_bus.publish(topic, event)

    # endregion

    # region Submit orders

    def submit_order(self, order: Order, broker: Broker) -> None:
        """Submit an order through the specified broker.

        Args:
            order: The order to submit.
            broker: The broker to submit the order through.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order is invalid or cannot be submitted.
        """
        broker.submit_order(order)

    def cancel_order(self, order: Order, broker: Broker) -> None:
        """Cancel an order through the specified broker.

        Args:
            order: The order to cancel.
            broker: The broker to cancel the order through.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order cannot be cancelled.
        """
        broker.cancel_order(order)

    def modify_order(self, order: Order, broker: Broker) -> None:
        """Modify an order through the specified broker.

        Args:
            order: The order to modify with updated parameters.
            broker: The broker to modify the order through.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order cannot be modified.
        """
        broker.modify_order(order)

    def get_active_orders(self, broker: Broker) -> List[Order]:
        """Get all active orders from the specified broker.

        Args:
            broker: The broker to get active orders from.

        Returns:
            List of all active orders for the specified broker.

        Raises:
            ConnectionError: If the broker is not connected.
        """
        return broker.get_active_orders()

    # endregion
