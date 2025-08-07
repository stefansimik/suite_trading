import logging
from datetime import datetime
from typing import Dict, List, Callable, Optional

from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.topic_factory import TopicFactory
from suite_trading.platform.market_data.event_feed_provider import EventFeedProvider
from suite_trading.platform.broker.broker import Broker
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.order.orders import Order
from suite_trading.strategy.strategy_state_machine import StrategyState, StrategyAction
from suite_trading.platform.engine.engine_state_machine import EngineState, EngineAction, create_engine_state_machine
from suite_trading.platform.engine.event_feed_manager import EventFeedManager

logger = logging.getLogger(__name__)


class TradingEngine:
    """Runs multiple trading strategies at the same time, each with its own timeline.

    TradingEngine lets you run many strategies together. Each strategy gets its own time
    and doesn't wait for other strategies. This means you can run old backtests and live
    trading at the same time.

    What you can do:
    - Run multiple backtests with different time periods at once
    - Mix live trading with historical testing
    - Each strategy moves through time based on its own events
    - Strategies don't interfere with each other
    """

    # region Lifecycle

    def __init__(self):
        """Create a new TradingEngine."""

        # Engine state machine
        self._state_machine = create_engine_state_machine()

        # Message bus
        self.message_bus = MessageBus()

        # EventFeedProvider registry
        self._event_feed_providers: Dict[str, EventFeedProvider] = {}

        # Brokers registry
        self._brokers: Dict[str, Broker] = {}

        # STRATEGIES
        # Strategies registry
        self._strategies: Dict[str, Strategy] = {}
        # EventFeeds management for each Strategy
        self._feed_manager = EventFeedManager()
        # Tracks time for each strategy
        self._strategy_current_time: Dict[Strategy, Optional[datetime]] = {}

    @property
    def state(self) -> EngineState:
        """Get what state the engine is in right now.

        Returns:
            EngineState: Current state like NEW, RUNNING, or STOPPED.
        """
        return self._state_machine.current_state

    def start(self):
        """Start the engine and all your strategies.

        Connects in this order: EventFeedProvider(s) -> Brokers first -> then starts all strategies.
        """
        # Check: engine must be in NEW state before starting
        if not self._state_machine.can_execute_action(EngineAction.START_ENGINE):
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise ValueError(f"Cannot start engine in state {self.state.name}. Valid actions: {valid_actions}")

        try:
            # Connect event-feed-providers first
            for provider_name, provider in self._event_feed_providers.items():
                provider.connect()
                logger.info(f"Connected event feed provider '{provider_name}'")

            # Connect brokers second
            for broker_name, broker in self._brokers.items():
                broker.connect()
                logger.info(f"Connected broker '{broker_name}'")

            # Start strategies last
            for strategy_name in list(self._strategies.keys()):
                self.start_strategy(strategy_name)
                logger.info(f"Started strategy under name: '{strategy_name}'")

            # Mark engine as running
            self._state_machine.execute_action(EngineAction.START_ENGINE)

            # Start processing events
            self.run_strategy_processing_loop()
        except Exception:
            # Mark engine as failed
            self._state_machine.execute_action(EngineAction.ERROR_OCCURRED)
            raise

    def stop(self):
        """Stop the engine and all your strategies.

        Stops all strategies first, then disconnects from brokers and event-feed-providers.
        Order: strategies → brokers → event-feed providers.

        Raises:
            ValueError: If engine is not in RUNNING state.
        """
        # Check: engine must be running before stopping
        if not self._state_machine.can_execute_action(EngineAction.STOP_ENGINE):
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise ValueError(f"Cannot stop engine in state {self.state.name}. Valid actions: {valid_actions}")

        try:
            # Stop all strategies and clean up their event-feeds first
            for strategy_name in list(self._strategies.keys()):
                self.stop_strategy(strategy_name)
                logger.info(f"Stopped strategy named '{strategy_name}'")

            # Disconnect brokers second
            for broker_name, broker in self._brokers.items():
                broker.disconnect()
                logger.info(f"Disconnected broker '{broker_name}'")

            # Disconnect event-feed-providers last
            for provider_name, provider in self._event_feed_providers.items():
                provider.disconnect()
                logger.info(f"Disconnected event feed provider '{provider_name}'")

            # Mark engine as stopped
            self._state_machine.execute_action(EngineAction.STOP_ENGINE)
        except Exception:
            # Mark engine as failed
            self._state_machine.execute_action(EngineAction.ERROR_OCCURRED)
            raise

    def run_strategy_processing_loop(self) -> None:
        """Process events for all strategies until they're finished.

        How it works:
        Each strategy gets events independently and have their own timeline.
        Strategies just process their events one-by-one and when all event-feeds are finished,
        strategy stops and is finished.

        What happens:
        1. For each strategy, find its oldest event from all its event-feeds
        2. Give that event to the strategy and update its time
        3. Keep going until all event-feeds are finished

        When more events have the same time `dt_event`, then event coming from first event-feed wins.

        The engine stops automatically when all event-feeds for all strategies are finished.

        Raises:
            ValueError: If engine is not in RUNNING state.
        """
        # Check: engine must be in RUNNING state
        if self.state != EngineState.RUNNING:
            raise ValueError(f"Cannot run processing loop because engine is not RUNNING. Current state: {self.state.name}")

        logger.info("Starting event processing loop")

        # Keep going while any strategy still has data to process
        while self._feed_manager.has_unfinished_feeds():
            # Go through each strategy
            for strategy in self._strategies.values():
                # Find the oldest event from all this strategy's event-feeds
                # If events have the same time, use the first feed (keeps request order)
                oldest_feed = self._feed_manager.get_next_event_feed_for_strategy(strategy)

                # Process the event if we found one
                if oldest_feed is not None:
                    # Get the event
                    consumed_event = oldest_feed.next()

                    # Update this strategy's time
                    self._strategy_current_time[strategy] = consumed_event.dt_event

                    # Send event to strategy
                    try:
                        strategy.on_event(consumed_event)
                    except Exception as e:
                        logger.error(f"Error processing event for strategy: {e}")
                        # Mark strategy as failed
                        strategy._state_machine.execute_action(StrategyAction.ERROR_OCCURRED)
                        strategy.on_error(e)

            # Remove finished event-feeds
            self._feed_manager.cleanup_finished_feeds()

        logger.info("Event processing loop completed - all feeds finished")

        # Stop the engine when all data is processed
        self.stop()

    # endregion

    # region Strategies

    def add_strategy(self, name: str, strategy: Strategy) -> None:
        """Add a strategy to the engine with a name.

        Give your strategy a name so you can easily identify it in logs and manage it later.

        Args:
            name: Unique name to identify this strategy.
            strategy: The strategy instance to add.

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

        # Connect strategy to this engine
        strategy._set_trading_engine(self)
        self._strategies[name] = strategy

        # Set up time tracking for this strategy
        self._strategy_current_time[strategy] = None

        # Set up EventFeed tracking for this strategy
        self._feed_manager.add_strategy(strategy)

        # Mark strategy as added
        strategy._state_machine.execute_action(StrategyAction.ADD_STRATEGY_TO_ENGINE)

    def start_strategy(self, name: str) -> None:
        """Start a strategy by its name.

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
        """Stop a strategy by its name and clean up its event-feeds.

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

        # Stop all event-feeds for this strategy first
        # Try to stop all feeds even if some fail, then report any errors
        feed_errors = self._feed_manager.cleanup_all_feeds_for_strategy(strategy)
        for error in feed_errors:
            logger.error(f"Error during feed cleanup for strategy '{name}': {error}")

        # Now stop the strategy itself
        try:
            strategy.on_stop()

            # Check: make sure all event-feeds stopped successfully
            if feed_errors:
                error_summary = "; ".join(feed_errors)
                raise RuntimeError(f"Strategy callback succeeded but event feed cleanup failed: {error_summary}")

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

        # Remove time tracking for this strategy
        if strategy in self._strategy_current_time:
            del self._strategy_current_time[strategy]

        # Remove EventFeed tracking for this strategy
        self._feed_manager.remove_strategy(strategy)

        # Remove from strategies' dictionary
        del self._strategies[name]

    @property
    def strategies(self) -> Dict[str, Strategy]:
        """Get all your strategies.

        Returns:
            Dictionary mapping strategy names to strategy instances.
        """
        return self._strategies

    # endregion

    # region EventFeed providers

    def add_event_feed_provider(self, name: str, provider: EventFeedProvider) -> None:
        """Add an event-feed provider to the engine with a name.

        Give your event-feed provider a name so you can easily identify it in logs and use it later.

        Args:
            name: Unique name to identify this provider.
            provider: The EventFeedProvider instance to add.

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
        """Remove an event-feed provider by name.

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
        """Get all your event-feed providers.

        Returns:
            Dictionary mapping provider names to provider instances.
        """
        return self._event_feed_providers

    # endregion

    # region Brokers

    def add_broker(self, name: str, broker: Broker) -> None:
        """Add a broker to the engine with a name.

        Give your broker a name so you can easily identify it in logs and use it later.

        Args:
            name: Unique name to identify this broker.
            broker: The broker instance to add.

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
        """Get all your brokers.

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
        """Ask for events to be sent to a strategy.

        Creates an event-feed for your strategy using one of your event-feed providers.
        The engine will manage this feed and send events to your strategy.

        Args:
            strategy: The strategy that wants to receive events.
            name: Unique name for this event-feed within the strategy.
            event_type: Type of events to receive (e.g., NewBarEvent).
            parameters: Dictionary with event-specific parameters.
            provider_ref: Name of the event-feed provider to use.
            callback: Function to call when events are received.

        Raises:
            ValueError: If $name is already in use for this strategy, $provider_ref not found,
                       or the EventFeed cannot be created for $event_type with $parameters.
        """
        # Check: strategy must be added to this engine
        if strategy not in self._strategies.values():
            raise ValueError(
                "Cannot call `request_event_delivery_for_strategy` because $strategy "
                f"({strategy.__class__.__name__}) is not added to this TradingEngine. "
                "Add the strategy using `add_strategy` first.",
            )

        # Check: delivery name must be unique per strategy
        feeds_list = self._feed_manager.get_event_feeds_for_strategy(strategy)
        for existing_feed in feeds_list:
            if existing_feed.request_info.get("name") == name:
                raise ValueError(
                    "Cannot call `request_event_delivery_for_strategy` because event-feed with $name "
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
        event_feed = provider.create_event_feed(event_type, parameters, callback)

        # Store request metadata including the name
        event_feed.request_info = {
            "name": name,
            "event_type": event_type,
            "parameters": parameters,
            "callback": callback,
            "provider_ref": provider_ref,
        }

        # Add EventFeed to strategy using manager (preserves request order)
        self._feed_manager.add_event_feed_for_strategy(strategy, event_feed)

    def cancel_event_delivery_for_strategy(self, strategy: Strategy, name: str) -> None:
        """Stop sending events to a strategy.

        Args:
            strategy: The strategy that owns the event-feed.
            name: Name of the event-feed to cancel.

        Raises:
            ValueError: If $name is not found for this strategy, or $strategy is not registered.
        """
        # Check: strategy must be added to this engine
        if strategy not in self._strategies.values():
            raise ValueError(
                "Cannot call `cancel_event_delivery_for_strategy` because $strategy "
                f"({strategy.__class__.__name__}) is not added to this TradingEngine. "
                "Add the strategy using `add_strategy` first.",
            )

        # Find and close the feed by name before removing
        feeds_list = self._feed_manager.get_event_feeds_for_strategy(strategy)
        feed_to_close = None
        for feed in feeds_list:
            if feed.request_info.get("name") == name:
                feed_to_close = feed
                break

        if feed_to_close is None:
            raise ValueError(
                "Cannot call `cancel_event_delivery_for_strategy` because delivery name $name "
                f"('{name}') does not exist for this strategy. Ensure the request was created "
                "with `request_event_delivery_for_strategy`.",
            )

        # Close the feed first
        try:
            feed_to_close.close()
        except Exception as e:
            logger.error(f"Error closing event feed '{name}' for strategy: {e}")

        # Remove from manager
        self._feed_manager.remove_event_feed_for_strategy(strategy, name)

    def get_event_feeds_for_strategy(self, strategy: Strategy) -> List[EventFeed]:
        """Get all event-feeds for a strategy in the order you requested them.

        Args:
            strategy: The strategy to get event-feeds for.

        Returns:
            List[EventFeed]: Event-feeds in request order.

        Raises:
            ValueError: If $strategy is not added to this TradingEngine.
        """
        # Check: strategy must be added to this engine
        if strategy not in self._strategies.values():
            raise ValueError(
                "Cannot call `get_event_feeds_for_strategy` because $strategy "
                f"({strategy.__class__.__name__}) is not added to this TradingEngine. "
                "Add the strategy using `add_strategy` first.",
            )

        # Delegate to manager (returns copy to prevent external modification)
        return self._feed_manager.get_event_feeds_for_strategy(strategy)

    # endregion

    # region Orders

    def submit_order(self, order: Order, broker: Broker) -> None:
        """Send an order to your broker.

        Args:
            order: The order to submit.
            broker: The broker to use.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order is invalid or cannot be submitted.
        """
        broker.submit_order(order)

    def cancel_order(self, order: Order, broker: Broker) -> None:
        """Cancel an order with your broker.

        Args:
            order: The order to cancel.
            broker: The broker to use.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order cannot be cancelled.
        """
        broker.cancel_order(order)

    def modify_order(self, order: Order, broker: Broker) -> None:
        """Change an order with your broker.

        Args:
            order: The order to modify with updated parameters.
            broker: The broker to use.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order cannot be modified.
        """
        broker.modify_order(order)

    def get_active_orders(self, broker: Broker) -> List[Order]:
        """Get all your active orders from a broker.

        Args:
            broker: The broker to get active orders from.

        Returns:
            List of all active orders for this broker.

        Raises:
            ConnectionError: If the broker is not connected.
        """
        return broker.get_active_orders()

    # endregion

    # region Helper methods

    def publish_bar(self, bar: Bar, provider_name: str, is_historical: bool = True) -> None:
        """Send bar data to all strategies that want it.

        Creates an event and sends it to strategies through the message system.

        Args:
            bar: The bar data to send.
            provider_name: Name of the provider that created this bar.
            is_historical: Whether this bar data is historical or live. Defaults to True.
        """
        event = NewBarEvent(bar=bar, dt_received=datetime.now(), is_historical=is_historical, provider_name=provider_name)
        topic = TopicFactory.create_topic_for_bar(bar.bar_type)
        self.message_bus.publish(topic, event)

    # endregion
