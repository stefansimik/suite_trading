import logging
from datetime import datetime
from typing import Dict, List, Callable, Optional

from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.market_data.event_feed_provider import EventFeedProvider
from suite_trading.platform.broker.broker import Broker
from suite_trading.domain.order.orders import Order
from suite_trading.strategy.strategy_state_machine import StrategyState, StrategyAction
from suite_trading.platform.engine.engine_state_machine import EngineState, EngineAction, create_engine_state_machine
from suite_trading.platform.engine.event_feed_manager import EventFeedManager

logger = logging.getLogger(__name__)


class TradingEngine:
    """Runs multiple trading strategies at the same time, each with its own timeline.

    TradingEngine lets you run many strategies together. Each strategy has its own
    independent timeline and processes events at its own pace.

    How timelines work:
    A timeline is simply a date range (from-until) that a strategy processes events through.
    The engine creates a combined timeline from all event-feeds across all strategies.
    This timeline starts with the first event from any event-feed and ends with the
    last event from any event-feed. Each strategy moves through this timeline based
    only on the events it receives.

    What you can do:
    - Run multiple backtests with different time periods at once
    - Mix live trading with historical testing strategies
    - Each strategy processes its own events independently

    By default, strategies work independently and don't interact with each other.
    However, you can program strategies to communicate if needed - each strategy
    simply follows its own timeline based on the events it gets.
    """

    # region Init engine

    def __init__(self):
        """Create a new TradingEngine."""

        # Engine state machine
        self._state_machine = create_engine_state_machine()

        # EventFeedProvider registry
        self._event_feed_providers: Dict[str, EventFeedProvider] = {}

        # Brokers registry
        self._brokers: Dict[str, Broker] = {}

        # STRATEGIES
        # Strategies registry
        self._strategies: Dict[str, Strategy] = {}
        # EventFeeds management for each Strategy
        self._feed_manager = EventFeedManager()
        # Tracks last event time (timeline) per strategy
        self._strategy_last_event_time: Dict[Strategy, Optional[datetime]] = {}
        # Tracks latest known wall clock time per strategy (max of dt_received)
        self._strategy_wall_clock_time: Dict[Strategy, Optional[datetime]] = {}

    # endregion

    # region Query state

    @property
    def state(self) -> EngineState:
        """Get the current engine state.

        Returns:
            EngineState: Current state (NEW, RUNNING, or STOPPED).
        """
        return self._state_machine.current_state

    # endregion

    # region EventFeedProvider(s)

    def add_event_feed_provider(self, name: str, provider: EventFeedProvider) -> None:
        """Add an event feed provider with a unique name.

        Args:
            name: Unique name to identify this provider.
            provider: The EventFeedProvider instance to add.

        Raises:
            ValueError: If a provider with the same name already exists.
        """
        # Check: provider name must be unique and not already added
        if name in self._event_feed_providers:
            raise ValueError(
                f"EventFeedProvider with provider name $name ('{name}') is already added to this TradingEngine. Choose a different name.",
            )

        self._event_feed_providers[name] = provider

    def remove_event_feed_provider(self, name: str) -> None:
        """Remove an event feed provider by name.

        Args:
            name: Name of the provider to remove.

        Raises:
            KeyError: If no provider with the given name exists.
        """
        # Check: provider name must be added before removing
        if name not in self._event_feed_providers:
            raise KeyError(
                f"Cannot call `remove_event_feed_provider` because provider name $name ('{name}') is not added to this TradingEngine. Add the provider using `add_event_feed_provider` first.",
            )

        del self._event_feed_providers[name]

    @property
    def event_feed_providers(self) -> Dict[str, EventFeedProvider]:
        """Get all event feed providers.

        Returns:
            Dictionary mapping provider names to provider instances.
        """
        return self._event_feed_providers

    # endregion

    # region Brokers

    def add_broker(self, name: str, broker: Broker) -> None:
        """Add a broker with a unique name.

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
        """Get all brokers.

        Returns:
            Dictionary mapping broker names to broker instances.
        """
        return self._brokers

    # endregion

    # region Strategies

    def add_strategy(self, name: str, strategy: Strategy) -> None:
        """Add a strategy with a unique name.

        Args:
            name: Unique name to identify this strategy.
            strategy: The strategy instance to add.

        Raises:
            ValueError: If a strategy with the same name already exists or strategy is not NEW.
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

        # Set up last-event-time tracking for this strategy
        self._strategy_last_event_time[strategy] = None

        # Set up wall-clock-time tracking for this strategy
        self._strategy_wall_clock_time[strategy] = None

        # Set up EventFeed tracking for this strategy
        self._feed_manager.add_strategy(strategy)

        # Mark strategy as added
        strategy._state_machine.execute_action(StrategyAction.ADD_STRATEGY_TO_ENGINE)

    def start_strategy(self, name: str) -> None:
        """Start a strategy with specified name.

        Args:
            name: Name of the strategy to start.

        Raises:
            KeyError: If no strategy with the given name exists.
            ValueError: If strategy is not in ADDED state.
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
        """Stop a strategy by name and clean up its event feeds.

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
            ValueError: If strategy is not in terminal state.
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

        # Remove last-event-time tracking for this strategy
        if strategy in self._strategy_last_event_time:
            del self._strategy_last_event_time[strategy]

        # Remove wall-clock-time tracking for this strategy
        if strategy in self._strategy_wall_clock_time:
            del self._strategy_wall_clock_time[strategy]

        # Remove EventFeed tracking for this strategy
        self._feed_manager.remove_strategy(strategy)

        # Remove from strategies' dictionary
        del self._strategies[name]

        # Detach engine reference from this strategy
        strategy._clear_trading_engine()

    @property
    def strategies(self) -> Dict[str, Strategy]:
        """Get all strategies.

        Returns:
            Dictionary mapping strategy names to strategy instances.
        """
        return self._strategies

    # endregion

    # region EventFeed(s)

    def add_event_feed_for_strategy(
        self,
        strategy: Strategy,
        feed_name: str,
        event_feed: EventFeed,
        callback: Callable,
    ) -> None:
        """Attach an EventFeed to a strategy and register metadata.

        Args:
            strategy: The strategy that will receive events. Type: Strategy.
            feed_name: Unique name for this event-feed within the strategy. Type: str.
            event_feed: The EventFeed instance to manage. Type: EventFeed.
            callback: Function to call when events are received. Type: Callable.

        Raises:
            ValueError: If $strategy is not added to this TradingEngine or $feed_name is duplicate.
        """
        # Check: strategy must be added to this engine
        if strategy not in self._strategies.values():
            raise ValueError(
                "Cannot call `add_event_feed_for_strategy` because $strategy "
                f"({strategy.__class__.__name__}) is not added to this TradingEngine. "
                "Add the strategy using `add_strategy` first.",
            )

        # Check: feed_name must be unique per strategy
        if self._feed_manager.has_feed_name(strategy, feed_name):
            raise ValueError(
                "Cannot call `add_event_feed_for_strategy` because event-feed with $feed_name "
                f"('{feed_name}') is already used for this strategy. Choose a different name.",
            )

        # Timeline filtering if the strategy already processed events
        if strategy.last_event_time is not None:
            removed_count = event_feed.remove_events_before(strategy.last_event_time)
            if removed_count > 0:
                logger.info(
                    f"Filtered {removed_count} obsolete events before {strategy.last_event_time} to keep timeline",
                )

        # Register the feed with metadata in the manager
        self._feed_manager.add_event_feed_for_strategy(
            strategy=strategy,
            feed_name=feed_name,
            event_feed=event_feed,
            callback=callback,
        )

    def remove_event_feed_from_strategy(self, strategy: Strategy, feed_name: str) -> None:
        """Detach and close a feed by name for a strategy.

        Args:
            strategy: The strategy that owns the event-feed.
            feed_name: Name of the event-feed to remove.

        Raises:
            ValueError: If $strategy is not registered.
        """
        # Check: strategy must be added to this engine
        if strategy not in self._strategies.values():
            raise ValueError(
                "Cannot call `remove_event_feed_from_strategy` because $strategy "
                f"({strategy.__class__.__name__}) is not added to this TradingEngine. "
                "Add the strategy using `add_strategy` first.",
            )

        # Find and close the feed by name before removing
        feed_to_close = self._feed_manager.get_event_feed_by_name(strategy, feed_name)

        # Handle case where feed doesn't exist (already finished/removed)
        if feed_to_close is None:
            logger.debug(
                f"Event feed '{feed_name}' for strategy {strategy.__class__.__name__} was already finished or removed - no action needed",
            )
            return

        # Close the feed first
        try:
            feed_to_close.close()
        except Exception as e:
            logger.error(f"Error closing event feed '{feed_name}' for strategy: {e}")

        # Remove from manager
        self._feed_manager.remove_event_feed_for_strategy(strategy, feed_name)

    # endregion

    # region Run engine

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
            self.run_event_processing_loop()
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
        # Check: allow idempotent stop when already STOPPED; otherwise must be able to stop
        if self.state == EngineState.STOPPED:
            return

        # Check: engine must be in RUNNING state, when we want to stop it
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

    def run_event_processing_loop(self) -> None:
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

        # Keep going while any strategy still has any unfinished event-feeds
        while self._feed_manager.has_unfinished_feeds():
            # Go through each strategy
            for strategy in self._strategies.values():
                # Find the oldest event from all this strategy's event-feeds
                # If events have the same time, use the first feed (keeps order how EventFeeds were added)
                oldest_feed = self._feed_manager.get_next_event_feed_for_strategy(strategy)

                # Process the event if we found one
                if oldest_feed is not None:
                    # Get the event
                    consumed_event = oldest_feed.pop()

                    # Update this strategy's last event time (timeline)
                    self._strategy_last_event_time[strategy] = consumed_event.dt_event

                    # Update wall-clock-time with monotonic max of dt_received
                    prev = self._strategy_wall_clock_time.get(strategy)
                    if prev is None or consumed_event.dt_received > prev:
                        self._strategy_wall_clock_time[strategy] = consumed_event.dt_received

                    # Send event via stored callback (fallback to strategy.on_event)
                    callback = self._feed_manager.get_callback_for_feed(oldest_feed)
                    try:
                        callback(consumed_event)
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
