import logging
from datetime import datetime
from typing import Dict, List, Callable

from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.topic_factory import TopicFactory
from suite_trading.platform.market_data.market_data_provider import EventFeedProvider
from suite_trading.platform.broker.broker import Broker
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.order.orders import Order
from suite_trading.strategy.strategy_state_machine import StrategyState, StrategyAction
from suite_trading.platform.engine.engine_state_machine import EngineState, EngineAction, create_engine_state_machine

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
        # Engine state machine
        self._state_machine = create_engine_state_machine()

        # Message bus
        self.message_bus = MessageBus()

        # Strategy management
        self._strategies: Dict[str, Strategy] = {}

        # EventFeedProvider registry
        self._event_feed_providers: Dict[str, EventFeedProvider] = {}

        # Broker registry
        self._brokers: Dict[str, Broker] = {}

        # Event feed management - track event-feeds per strategy
        self._strategy_event_feeds: Dict[Strategy, Dict[str, EventFeed]] = {}

    @property
    def state(self) -> EngineState:
        """Get current lifecycle state.

        Returns:
            EngineState: Current lifecycle state of this engine.
        """
        return self._state_machine.current_state

    def start(self):
        """Start the TradingEngine and all strategies.

        This method connects all event feed providers and brokers, then starts all registered strategies.
        The startup order is: event feed providers → brokers → strategies.

        Raises:
            ValueError: If engine is not in NEW state.
        """
        # Check: engine must be in NEW state before starting
        if not self._state_machine.can_execute_action(EngineAction.START_ENGINE):
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise ValueError(f"Cannot start engine in state {self.state.name}. Valid actions: {valid_actions}")

        try:
            # Connect all event feed providers first
            for provider_name, provider in self._event_feed_providers.items():
                provider.connect()
                logger.info(f"Connected event feed provider '{provider_name}'")

            # Connect all brokers second
            for broker_name, broker in self._brokers.items():
                broker.connect()
                logger.info(f"Connected broker '{broker_name}'")

            # Start strategies last
            for strategy_name in list(self._strategies.keys()):
                self.start_strategy(strategy_name)
                logger.info(f"Started strategy under name: '{strategy_name}'")

            # Transition to RUNNING state after successful start
            self._state_machine.execute_action(EngineAction.START_ENGINE)
        except Exception:
            # Transition to ERROR state on any failure
            self._state_machine.execute_action(EngineAction.ERROR_OCCURRED)
            raise

    def stop(self):
        """Stop the TradingEngine and all strategies.

        This method stops all registered strategies, disconnects brokers, and disconnects event feed providers.
        The shutdown order is: strategies → brokers → event feed providers.

        Raises:
            ValueError: If engine is not in RUNNING state.
        """
        # Check: engine must be running before stopping
        if not self._state_machine.can_execute_action(EngineAction.STOP_ENGINE):
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise ValueError(f"Cannot stop engine in state {self.state.name}. Valid actions: {valid_actions}")

        try:
            # Stop all strategies and clean up their event feeds first
            for strategy_name in list(self._strategies.keys()):
                self.stop_strategy(strategy_name)
                logger.info(f"Stopped strategy named '{strategy_name}'")

            # Disconnect all brokers second
            for broker_name, broker in self._brokers.items():
                broker.disconnect()
                logger.info(f"Disconnected broker '{broker_name}'")

            # Disconnect all event feed providers last
            for provider_name, provider in self._event_feed_providers.items():
                provider.disconnect()
                logger.info(f"Disconnected event feed provider '{provider_name}'")

            # Transition to STOPPED state after successful stop
            self._state_machine.execute_action(EngineAction.STOP_ENGINE)
        except Exception:
            # Transition to ERROR state on any failure
            self._state_machine.execute_action(EngineAction.ERROR_OCCURRED)
            raise

    # endregion

    # region Strategies

    def add_strategy(self, name: str, strategy: Strategy) -> None:
        """Register a strategy with the specified name.

        Args:
            name: Unique name to identify this strategy.
            strategy: The strategy instance to register.

        Raises:
            ValueError: If a strategy with the same name already exists or $strategy is not NEW.
        """
        # Check: strategy name must be unique and not already added
        if name in self._strategies:
            raise ValueError(
                f"Cannot call `add_strategy` because strategy name $name ('{name}') is already added to this TradingEngine. Choose a different name.",
            )

        # Check: strategy must be NEW before attaching
        if strategy.state != StrategyState.NEW:
            raise ValueError(
                "Cannot call `add_strategy` because $strategy is not NEW. Current $state is "
                f"{strategy.state.name}. Provide a fresh instance of "
                f"{strategy.__class__.__name__}.",
            )

        # Attach engine reference to strategy (no state change here)
        strategy._set_trading_engine(self)
        self._strategies[name] = strategy

        # Initialize empty event feed tracking for this strategy
        self._strategy_event_feeds[strategy] = {}

        # Transition strategy lifecycle to ADDED after successful registration
        strategy._state_machine.execute_action(StrategyAction.ADD_STRATEGY_TO_ENGINE)

    def start_strategy(self, name: str) -> None:
        """Start a specific strategy by name.

        Args:
            name: Name of the strategy to start.

        Raises:
            KeyError: If no strategy with the given name exists.
            ValueError: If $state is not ADDED.
        """
        # Check: strategy name must be added before starting
        if name not in self._strategies:
            raise KeyError(
                f"Cannot call `start_strategy` because strategy name $name ('{name}') is not added to this TradingEngine. Add the strategy using `add_strategy` first.",
            )

        strategy = self._strategies[name]

        # Check: strategy must be able to start
        if not strategy._state_machine.can_execute_action(StrategyAction.START_STRATEGY):
            valid_actions = [a.value for a in strategy._state_machine.get_valid_actions()]
            raise ValueError(
                f"Cannot start strategy in state {strategy.state.name}. Valid actions: {valid_actions}",
            )

        try:
            strategy.on_start()
            strategy._state_machine.execute_action(StrategyAction.START_STRATEGY)
        except Exception:
            strategy._state_machine.execute_action(StrategyAction.ERROR_OCCURRED)
            raise

    def stop_strategy(self, name: str) -> None:
        """Stop a specific strategy by name and clean up its event feeds.

        Args:
            name: Name of the strategy to stop.

        Raises:
            KeyError: If no strategy with the given name exists.
            ValueError: If $state is not RUNNING.
        """
        # Check: strategy name must be added before stopping
        if name not in self._strategies:
            raise KeyError(
                f"Cannot call `stop_strategy` because strategy name $name ('{name}') is not added to this TradingEngine. Add the strategy using `add_strategy` first.",
            )

        strategy = self._strategies[name]

        # Check: strategy must be able to stop
        if not strategy._state_machine.can_execute_action(StrategyAction.STOP_STRATEGY):
            valid_actions = [a.value for a in strategy._state_machine.get_valid_actions()]
            raise ValueError(
                f"Cannot stop strategy in state {strategy.state.name}. Valid actions: {valid_actions}",
            )

        # Stop all registered event feeds for this strategy first
        feed_entries = self._strategy_event_feeds.get(strategy, {})
        for feed_name, entry in list(feed_entries.items()):
            try:
                entry["feed"].stop()
            except Exception as e:
                logger.error(f"Error stopping event feed '{feed_name}' for strategy '{name}': {e}")

        # Clear strategy event feed tracking after stopping all feeds
        self._strategy_event_feeds[strategy] = {}

        # Then invoke strategy's on_stop callback and transition state
        try:
            strategy.on_stop()
            strategy._state_machine.execute_action(StrategyAction.STOP_STRATEGY)
        except Exception:
            strategy._state_machine.execute_action(StrategyAction.ERROR_OCCURRED)
            raise

    def remove_strategy(self, name: str) -> None:
        """Remove a strategy by name.

        Args:
            name: Name of the strategy to remove.

        Raises:
            KeyError: If no strategy with the given name exists.
            ValueError: If $state is not STOPPED.
        """
        # Check: strategy name must be added before removing
        if name not in self._strategies:
            raise KeyError(
                f"Cannot call `remove_strategy` because strategy name $name ('{name}') is not added to this TradingEngine. Add the strategy using `add_strategy` first.",
            )

        strategy = self._strategies[name]

        # Check: strategy must be in terminal state before removing
        if not strategy.is_in_terminal_state():
            valid_actions = [a.value for a in strategy._state_machine.get_valid_actions()]
            raise ValueError(
                f"Cannot call `remove_strategy` because $state ({strategy.state.name}) is not terminal. Valid actions: {valid_actions}",
            )

        # Remove any remaining event feed tracking for safety
        if strategy in self._strategy_event_feeds:
            del self._strategy_event_feeds[strategy]

        # Remove from strategies' dictionary
        del self._strategies[name]

    @property
    def strategies(self) -> Dict[str, Strategy]:
        """Get all registered strategies.

        Returns:
            Dictionary mapping strategy names to strategy instances.
        """
        return self._strategies

    # endregion

    # region EventFeed providers

    def add_event_feed_provider(self, name: str, provider: EventFeedProvider) -> None:
        """Register an EventFeedProvider with the specified name.

        Args:
            name: Unique name to identify this provider.
            provider: The EventFeedProvider instance to register.

        Raises:
            ValueError: If a provider with the same $name already exists.
        """
        # Check: provider name must be unique and not already added
        if name in self._event_feed_providers:
            raise ValueError(
                f"EventFeedProvider with provider name $name ('{name}') is already added to this TradingEngine. Choose a different name.",
            )

        self._event_feed_providers[name] = provider

    def remove_event_feed_provider(self, name: str) -> None:
        """Remove an EventFeedProvider by $name.

        Args:
            name: Name of the provider to remove.

        Raises:
            KeyError: If no provider with the given $name exists.
        """
        # Check: provider name must be added before removing
        if name not in self._event_feed_providers:
            raise KeyError(
                f"Cannot call `remove_event_feed_provider` because provider name $name ('{name}') is not added to this TradingEngine. Add the provider using `add_event_feed_provider` first.",
            )

        del self._event_feed_providers[name]

    @property
    def event_feed_providers(self) -> Dict[str, EventFeedProvider]:
        """Get all registered EventFeedProviders.

        Returns:
            Dictionary mapping provider $name values to provider instances.
        """
        return self._event_feed_providers

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
        # Check: broker name must be unique and not already added
        if name in self._brokers:
            raise ValueError(f"Broker with broker name $name ('{name}') is already added to this TradingEngine. Choose a different name.")

        self._brokers[name] = broker

    def remove_broker(self, name: str) -> None:
        """Remove a broker by name.

        Args:
            name: Name of the broker to remove.

        Raises:
            KeyError: If no broker with the given name exists.
        """
        # Check: broker name must be added before removing
        if name not in self._brokers:
            raise KeyError(
                f"Cannot call `remove_broker` because broker name $name ('{name}') is not added to this TradingEngine. Add the broker using `add_broker` first.",
            )

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
        provider_ref: str,
        callback: Callable,
    ) -> None:
        """Request event delivery for the specified strategy.

        This method creates and registers an event feed for a strategy using a selected
        EventFeedProvider. The EventFeedProvider returns an opaque feed object that TradingEngine
        stores and manages for lifecycle events (cancel/stop).

        Args:
            strategy: The strategy requesting the event delivery.
            name: Unique name for this delivery within the strategy.
            event_type: Type of events to receive (e.g., NewBarEvent).
            parameters: Dictionary with event-specific parameters.
            provider_ref: Reference name of the provider to use for this delivery.
            callback: Function to call when events are received. Keyword-only.

        Raises:
            ValueError: If $name is already in use for this strategy or $provider_ref not found.
            UnsupportedEventTypeError: If provider doesn't support the $event_type.
            UnsupportedConfigurationError: If provider doesn't support the configuration.
        """
        # Check: strategy must be added to this engine
        if strategy not in self._strategy_event_feeds:
            raise ValueError(
                "Cannot call `request_event_delivery_for_strategy` because $strategy "
                f"({strategy.__class__.__name__}) is not added to this TradingEngine. "
                "Add the strategy using `add_strategy` first.",
            )

        # Check: delivery name must be unique per strategy
        if name in self._strategy_event_feeds[strategy]:
            raise ValueError(
                "Cannot call `request_event_delivery_for_strategy` because delivery name $name "
                f"('{name}') is already used for this strategy. Choose a different name.",
            )

        # Check: provider must exist in added event feed providers
        if provider_ref not in self._event_feed_providers:
            raise ValueError(
                "Cannot call `request_event_delivery_for_strategy` because provider reference $provider_ref "
                f"('{provider_ref}') was not found among added event feed providers. "
                "Add the provider using `add_event_feed_provider` or use a correct reference.",
            )

        provider = self._event_feed_providers[provider_ref]

        # Obtain event feed instance from provider (may raise provider-specific errors)
        # Note: The provider should create a feed that stores request info internally
        event_feed = provider.get_event_feed(event_type, parameters, callback)

        # Store request metadata in the feed's request_info if it doesn't have it
        event_feed.request_info = {
            "event_type": event_type,
            "parameters": parameters,
            "callback": callback,
            "provider_ref": provider_ref,
        }

        # Track the event feed directly (simplified structure)
        self._strategy_event_feeds[strategy][name] = event_feed

    def cancel_event_delivery_for_strategy(self, strategy: Strategy, name: str) -> None:
        """Cancel event delivery for the specified strategy.

        Args:
            strategy: The strategy that owns the event delivery.
            name: Name of the delivery to cancel.

        Raises:
            ValueError: If $name is not found for this strategy, or $strategy is not registered.
        """
        # Check: strategy must be added to this engine
        if strategy not in self._strategy_event_feeds:
            raise ValueError(
                "Cannot call `cancel_event_delivery_for_strategy` because $strategy "
                f"({strategy.__class__.__name__}) is not added to this TradingEngine. "
                "Add the strategy using `add_strategy` first.",
            )

        # Check: delivery name must exist for this strategy
        if name not in self._strategy_event_feeds[strategy]:
            raise ValueError(
                "Cannot call `cancel_event_delivery_for_strategy` because delivery name $name "
                f"('{name}') does not exist for this strategy. Ensure the request was created "
                "with `request_event_delivery_for_strategy`.",
            )

        feed = self._strategy_event_feeds[strategy][name]
        try:
            feed.close()
        except Exception as e:
            logger.error(f"Error closing event feed '{name}' for strategy: {e}")

        # Remove from tracking regardless of close outcome
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
