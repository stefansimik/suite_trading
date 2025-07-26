import logging
from datetime import datetime
from typing import Dict, List, Sequence
from suite_trading.strategy.base import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.topic_factory import TopicFactory
from suite_trading.platform.market_data.market_data_provider import MarketDataProvider
from suite_trading.platform.broker.broker import Broker
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.order.orders import Order

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

    # TODO: Reevaluate, if we need this convenience method at all / + if location is OK
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

    # -----------------------------------------------
    # MARKET DATA PROVIDER MANAGEMENT
    # -----------------------------------------------

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

    def get_historical_bars_series(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: datetime,
        provider: MarketDataProvider,
    ) -> Sequence[Bar]:
        """Get all historical bars at once for strategy initialization and analysis.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
            from_dt: Start datetime for the data range.
            until_dt: End datetime for the data range.
            provider: The market data provider to use for this request.

        Returns:
            Sequence of Bar objects containing historical market data.
        """
        return provider.get_historical_bars_series(bar_type, from_dt, until_dt)

    def stream_historical_bars(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: datetime,
        provider: MarketDataProvider,
    ) -> None:
        """Stream historical bars one-by-one for memory-efficient backtesting.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
            from_dt: Start datetime for the data range.
            until_dt: End datetime for the data range.
            provider: The market data provider to use for this request.
        """
        # TODO: Reevaluate, how this should work
        provider.stream_historical_bars(bar_type, from_dt, until_dt)

    def subscribe_to_live_bars_with_history(
        self,
        bar_type: BarType,
        history_days: int,
        strategy: Strategy,
        provider: MarketDataProvider,
    ) -> None:
        """Subscribe to live bars with seamless historical-to-live transition.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
            history_days: Number of days before now to include historical data.
            strategy: The strategy that wants to subscribe.
            provider: The market data provider to use for this request.
        """
        # Initialize subscription set for this bar type if needed
        if bar_type not in self._bar_subscriptions:
            self._bar_subscriptions[bar_type] = set()

        # Check if this is the first subscriber for this bar type
        is_first_subscriber = len(self._bar_subscriptions[bar_type]) == 0

        # Add strategy to subscription tracking
        self._bar_subscriptions[bar_type].add(strategy)

        # Subscribe strategy to MessageBus topic
        topic = TopicFactory.create_topic_for_bar(bar_type)
        self.message_bus.subscribe(topic, strategy.on_event)

        # TODO: Reevaluate, how this should work
        # Start receiving bars with history from market data provider
        if is_first_subscriber:
            provider.subscribe_to_live_bars_with_history(bar_type, history_days)

    # -----------------------------------------------
    # BROKER MANAGEMENT
    # -----------------------------------------------

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

    # -----------------------------------------------
    # ORDER MANAGEMENT
    # -----------------------------------------------

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

    # -----------------------------------------------
    # MARKET DATA SUBSCRIPTION MANAGEMENT
    # -----------------------------------------------

    # TODO: Reevaluate, how this should work
    def subscribe_to_live_bars(self, bar_type: BarType, strategy: Strategy):
        """Subscribe a strategy to live bar data for a specific bar type.

        This method handles all the technical details of subscription:
        - Subscribes the strategy to the MessageBus topic
        - Tracks which strategies are subscribed to which bar types
        - Initiates data publishing when first strategy subscribes

        Args:
            bar_type (BarType): The type of bar to subscribe to.
            strategy (Strategy): The strategy that wants to subscribe.

        Raises:
            RuntimeError: If no market data provider is set.
        """
        if self._market_data_provider is None:
            raise RuntimeError(
                f"Cannot call `subscribe_to_live_bars` for $bar_type ({bar_type}) because $market_data_provider is None. Set a market data provider when creating TradingEngine.",
            )

        # Initialize subscription set for this bar type if needed
        if bar_type not in self._bar_subscriptions:
            self._bar_subscriptions[bar_type] = set()

        # Check if this is the first subscriber for this bar type
        is_first_subscriber = len(self._bar_subscriptions[bar_type]) == 0

        # Add strategy to subscription tracking
        self._bar_subscriptions[bar_type].add(strategy)

        # Subscribe strategy to MessageBus topic
        topic = TopicFactory.create_topic_for_bar(bar_type)
        self.message_bus.subscribe(topic, strategy.on_event)

        # Start receiving live bars from market data provider
        if is_first_subscriber:
            self._market_data_provider.subscribe_to_live_bars(bar_type)

    def unsubscribe_from_live_bars(self, bar_type: BarType, strategy: Strategy):
        """Unsubscribe a strategy from live bar data for a specific bar type.

        This method handles cleanup when a strategy unsubscribes:
        - Unsubscribes the strategy from the MessageBus topic
        - Removes strategy from subscription tracking
        - Stops data publishing when last strategy unsubscribes

        Args:
            bar_type (BarType): The type of bar to unsubscribe from.
            strategy (Strategy): The strategy that wants to unsubscribe.
        """
        # Check if we have subscriptions for this bar type
        if bar_type not in self._bar_subscriptions:
            logger.warning(
                f"Cannot call `unsubscribe_from_live_bars` for $bar_type ({bar_type}) and $strategy ('{strategy.name}') because no subscriptions exist for this bar type. This likely indicates a logical mistake - trying to unsubscribe from something that was never subscribed to.",
            )
            return

        # Remove strategy from subscription tracking
        self._bar_subscriptions[bar_type].discard(strategy)

        # Unsubscribe strategy from MessageBus topic
        topic = TopicFactory.create_topic_for_bar(bar_type)
        self.message_bus.unsubscribe(topic, strategy.on_event)

        # Check if this was the last subscriber
        if len(self._bar_subscriptions[bar_type]) == 0:
            # Clean up empty subscription set
            del self._bar_subscriptions[bar_type]

            # Stop requesting live bars from market data provider
            if self._market_data_provider is not None:
                self._market_data_provider.unsubscribe_from_live_bars(bar_type)
