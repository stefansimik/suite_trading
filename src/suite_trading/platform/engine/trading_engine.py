import logging
from datetime import datetime
from typing import Dict, List, Callable, Any
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.topic_factory import TopicFactory
from suite_trading.platform.market_data.market_data_provider import MarketDataProvider
from suite_trading.platform.broker.broker import Broker
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

    # region Lifecycle

    def __init__(self):
        """Initialize a new TradingEngine instance.

        Creates its own MessageBus instance for isolated operation.
        """
        # Engine state and core components
        self._is_running: bool = False
        self.message_bus = MessageBus()

        # Strategy management
        self._strategies: Dict[str, Strategy] = {}

        # Market data provider management
        self._market_data_providers: Dict[str, MarketDataProvider] = {}

        # Broker management
        self._brokers: Dict[str, Broker] = {}

        # Event feed management - track feeds per strategy
        self._strategy_event_feeds: Dict[Strategy, Dict[str, Any]] = {}

    def start(self):
        """Start the TradingEngine and all strategies.

        This method starts all registered strategies.
        """
        self._is_running = True

        # Start strategies
        for name in list(self._strategies.keys()):
            self.start_strategy(name)

        # TODO:
        #   We should start / connect all brokers / market-data-providers
        #   The order is important, first are starting all market-data-providers, then all brokers, then strategies

    def stop(self):
        """Stop the TradingEngine and all strategies.

        This method stops all registered strategies and cleans up their event feeds.
        """
        self._is_running = False

        # Stop all strategies and clean up their event feeds
        for strategy_name in list(self._strategies.keys()):
            self.stop_strategy(strategy_name)

        # TODO:
        #   We should stop / disconnect all brokers / market-data-providers
        #   The order is important, first are stopping all strategies, then all brokers, then all market-data-providers

    # endregion

    # region Strategies

    def add_strategy(self, name: str, strategy: Strategy) -> None:
        """Register a strategy with the specified name.

        Args:
            name: Unique name to identify this strategy.
            strategy: The strategy instance to register.

        Raises:
            ValueError: If a strategy with the same name already exists.
        """
        if name in self._strategies:
            raise ValueError(f"Strategy with $name '{name}' already exists. Choose a different name.")

        # TODO: Let's check, if Strategy is in appropriate state (new, not started) to be added

        # Set the trading engine reference in the strategy
        strategy._set_trading_engine(self)
        self._strategies[name] = strategy

        # Initialize empty event feed tracking for this strategy
        self._strategy_event_feeds[strategy] = {}

    def start_strategy(self, name: str) -> None:
        """Start a specific strategy by name.

        Args:
            name: Name of the strategy to start.

        Raises:
            KeyError: If no strategy with the given name exists.
        """
        if name not in self._strategies:
            raise KeyError(f"No strategy with $name '{name}' is registered. Cannot start non-existent strategy.")

        # TODO: Let's check, if Strategy is in appropriate state (new, not started) to be started

        strategy = self._strategies[name]
        strategy.on_start()

    def stop_strategy(self, name: str) -> None:
        """Stop a specific strategy by name and clean up its event feeds.

        Args:
            name: Name of the strategy to stop.

        Raises:
            KeyError: If no strategy with the given name exists.
        """
        if name not in self._strategies:
            raise KeyError(f"No strategy with $name '{name}' is registered. Cannot stop non-existent strategy.")

        # TODO: Let's check, if Strategy is in appropriate state (had to be started & is not stopped) to be stopped

        strategy = self._strategies[name]

        # Stop all registered event feeds for this strategy first
        if strategy in self._strategy_event_feeds:
            feed_names = list(self._strategy_event_feeds[strategy].keys())
            for feed_name in feed_names:
                entry = self._strategy_event_feeds[strategy].get(feed_name, {})
                feed = entry.get("feed")
                try:
                    if feed is not None and hasattr(feed, "stop") and callable(getattr(feed, "stop")):
                        feed.stop()
                except Exception as e:
                    logger.error(f"Error stopping event feed '{feed_name}' for strategy: {e}")
            # Clear strategy event feed tracking after stopping all feeds
            self._strategy_event_feeds[strategy] = {}

        # Then invoke strategy's on_stop callback
        strategy.on_stop()

    def remove_strategy(self, name: str) -> None:
        """Remove a strategy by name.

        Args:
            name: Name of the strategy to remove.

        Raises:
            KeyError: If no strategy with the given name exists.
        """
        if name not in self._strategies:
            raise KeyError(f"No strategy with $name '{name}' is registered. Cannot remove non-existent strategy.")

        # TODO: Let's check, if Strategy is in appropriate state (stopped) to be removed

        # Remove from strategies dictionary
        del self._strategies[name]

    @property
    def strategies(self) -> Dict[str, Strategy]:
        """Get all registered strategies.

        Returns:
            Dictionary mapping strategy names to strategy instances.
        """
        return self._strategies

    # endregion

    # region Market data providers

    def add_market_data_provider(self, name: str, provider: MarketDataProvider) -> None:
        """Register a market data provider with the specified name.

        Args:
            name: Unique name to identify this provider.
            provider: The market data provider instance to register.

        Raises:
            ValueError: If a provider with the same name already exists.
        """
        if name in self._market_data_providers:
            raise ValueError(f"Market data provider with $name '{name}' already exists. Choose a different name.")

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

    # region Brokers

    def add_broker(self, name: str, broker: Broker) -> None:
        """Register a broker with the specified name.

        Args:
            name: Unique name to identify this broker.
            broker: The broker instance to register.

        Raises:
            ValueError: If a broker with the same name already exists.
        """
        if name in self._brokers:
            raise ValueError(f"Broker with $name '{name}' already exists. Choose a different name.")

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

    # region Event feeds

    def request_event_delivery_for_strategy(
        self,
        strategy: Strategy,
        name: str,
        event_type: type,
        parameters: dict,
        callback: Callable,
        provider_ref: str,
    ) -> None:
        """Request event delivery for the specified strategy.

        This method creates and registers an event feed for a strategy using a selected
        market data provider. The provider returns an opaque feed object that TradingEngine
        stores and manages for lifecycle events (cancel/stop).

        Args:
            strategy: The strategy requesting the event delivery.
            name: Unique name for this delivery within the strategy.
            event_type: Type of events to receive (e.g., NewBarEvent).
            parameters: Dictionary with event-specific parameters.
            callback: Function to call when events are received.
            provider_ref: Reference name of the provider to use for this delivery.

        Raises:
            ValueError: If $name is already in use for this strategy or $provider_ref not found.
            UnsupportedEventTypeError: If provider doesn't support the $event_type.
            UnsupportedConfigurationError: If provider doesn't support the configuration.
        """
        # Validate strategy is registered
        if strategy not in self._strategy_event_feeds:
            raise ValueError(
                "Cannot call `request_event_delivery_for_strategy` because $strategy "
                f"({strategy.__class__.__name__}) is not registered with this TradingEngine. "
                "Add the strategy using `add_strategy` first.",
            )

        # Validate name is unique for this strategy
        if name in self._strategy_event_feeds[strategy]:
            raise ValueError(
                "Cannot call `request_event_delivery_for_strategy` because $name "
                f"('{name}') is already used for this strategy. Choose a different name.",
            )

        # Validate provider exists
        if provider_ref not in self._market_data_providers:
            raise ValueError(
                "Cannot call `request_event_delivery_for_strategy` because $provider_ref "
                f"('{provider_ref}') was not found among registered $market_data_providers. "
                "Add the provider using `add_market_data_provider` or use a correct reference.",
            )

        provider = self._market_data_providers[provider_ref]

        # Obtain event feed instance from provider (may raise provider-specific errors)
        feed = provider.get_event_feed(event_type, parameters, callback)

        # Track the event feed
        self._strategy_event_feeds[strategy][name] = {
            "event_type": event_type,
            "parameters": parameters,
            "callback": callback,
            "provider_ref": provider_ref,
            "feed": feed,
        }

    def cancel_event_delivery_for_strategy(self, strategy: Strategy, name: str) -> None:
        """Cancel event delivery for the specified strategy.

        Args:
            strategy: The strategy that owns the event delivery.
            name: Name of the delivery to cancel.

        Raises:
            ValueError: If $name is not found for this strategy, or $strategy is not registered.
        """
        # Validate strategy is registered
        if strategy not in self._strategy_event_feeds:
            raise ValueError(
                "Cannot call `cancel_event_delivery_for_strategy` because $strategy "
                f"({strategy.__class__.__name__}) is not registered with this TradingEngine. "
                "Add the strategy using `add_strategy` first.",
            )

        # Validate feed exists
        if name not in self._strategy_event_feeds[strategy]:
            raise ValueError(
                "Cannot call `cancel_event_delivery_for_strategy` because $name "
                f"('{name}') does not exist for this strategy. Ensure the request was created "
                "with `request_event_delivery_for_strategy`.",
            )

        feed = self._strategy_event_feeds[strategy][name].get("feed")
        try:
            # TODO: This has to be updated (EventFeed will have some `stop` or `start` method in the future)
            if feed is not None and hasattr(feed, "stop") and callable(getattr(feed, "stop")):
                feed.stop()
        except Exception as e:
            logger.error(f"Error stopping event feed '{name}' for strategy: {e}")
        finally:
            # Remove from tracking regardless of stop outcome
            del self._strategy_event_feeds[strategy][name]

    # endregion

    # region Orders

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

    # region Helper methods

    def publish_bar(self, bar: Bar, provider_name: str, is_historical: bool = True) -> None:
        """Publish a bar to the MessageBus for distribution to subscribed strategies.

        Creates a NewBarEvent with the specified historical context and publishes it to the appropriate topic.

        Args:
            bar: The bar to publish.
            provider_name: Name of the provider that generated this bar.
            is_historical: Whether this bar data is historical or live. Defaults to True.
        """
        event = NewBarEvent(bar=bar, dt_received=datetime.now(), is_historical=is_historical, provider_name=provider_name)
        topic = TopicFactory.create_topic_for_bar(bar.bar_type)
        self.message_bus.publish(topic, event)

    # endregion
