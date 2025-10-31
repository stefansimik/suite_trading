from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, NamedTuple, TYPE_CHECKING

from suite_trading.domain.event import Event
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.market_data.event_feed_provider import EventFeedProvider
from suite_trading.platform.broker.broker import Broker
from suite_trading.domain.market_data.price_sample_source import PriceSampleSource
from suite_trading.platform.broker.capabilities import PriceSampleConsumer
from suite_trading.domain.order.orders import Order
from suite_trading.strategy.strategy_state_machine import StrategyState, StrategyAction
from suite_trading.platform.engine.engine_state_machine import EngineState, EngineAction, create_engine_state_machine
from bidict import bidict

from suite_trading.utils.state_machine import StateMachine
from suite_trading.platform.routing.strategy_broker_pair import StrategyBrokerPair

if TYPE_CHECKING:
    from suite_trading.domain.order.execution import Execution


logger = logging.getLogger(__name__)

# TODO
#  Fix all problems, where we are logging Strategies like this: `{strategy.__class__.__name__}`
#  This is not sufficient, as we can have more variously configured Strategy instances of the same class,
#  so we have to recognize them by name;
#  One option is to use bi-directional dictionary for 1:1 mapping between Strategies and their names.
#   We will need to implement this structure, but then using it will be simple like: `d[key]` or `d.inverse[value]`
#  Another possible action would be remove manual naming of Strategies and add to them abstract function: `get_unique_name()`

# region Helper classes


class EventFeedCallbackPair(NamedTuple):
    feed: EventFeed
    callback: Callable


## StrategyBrokerPair moved to routing module to avoid duplication and engine coupling.


@dataclass
class StrategyClocks:
    last_event_time: datetime | None = None
    wall_clock_time: datetime | None = None

    def update_on_event(self, dt_event: datetime, dt_received: datetime) -> None:
        # Advance timeline to official event time
        self.last_event_time = dt_event
        # Keep monotonic max of when the system received events
        if self.wall_clock_time is None or dt_received > self.wall_clock_time:
            self.wall_clock_time = dt_received


# endregion


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

    # region Init

    def __init__(self):
        """Create a new TradingEngine."""

        # Engine state machine
        self._engine_state_machine: StateMachine = create_engine_state_machine()

        # EventFeedProvider registry (type-keyed, one instance per class)
        self._event_feed_providers_by_type_dict: dict[type[EventFeedProvider], EventFeedProvider] = {}

        # Brokers registry (type-keyed, one instance per class)
        self._brokers_by_type_dict: dict[type[Broker], Broker] = {}
        # Brokers that consume price samples (capability-based)
        self._price_sample_consuming_brokers: list[PriceSampleConsumer] = []

        # Strategies registry (bi-directional dictionary)
        self._strategies_by_name_bidict: bidict[str, Strategy] = bidict()

        # EventFeeds per Strategy: strategy -> { feed_name: FeedAndCallbackTuple }
        self._event_feeds_by_strategy_dict: dict[Strategy, dict[str, EventFeedCallbackPair]] = {}

        # Tracks per-strategy clocks (last_event and wall-clock)
        self._clocks_by_strategy_dict: dict[Strategy, StrategyClocks] = {}

        # Keep relation of Order to: Strategy + Broker
        self._routing_by_order_dict: dict[Order, StrategyBrokerPair] = {}

        # Track executions per Strategy for later statistics
        self._executions_by_strategy_name_dict: dict[str, list[Execution]] = {}

    # endregion

    # region State

    @property
    def state(self) -> EngineState:
        """Get the current engine state.

        Returns:
            EngineState: Current state (NEW, RUNNING, or STOPPED).
        """
        return self._engine_state_machine.current_state

    # endregion

    # region EventFeedProvider(s)

    def add_event_feed_provider(self, provider: EventFeedProvider) -> None:
        """Add an event feed provider (one per provider class).

        Args:
            provider: The EventFeedProvider instance to add.

        Raises:
            ValueError: If a provider of the same class was already added.
        """
        key = type(provider)
        # Check: only one provider per concrete class
        if key in self._event_feed_providers_by_type_dict:
            raise ValueError(
                f"Cannot call `add_event_feed_provider` because a provider of class {key.__name__} is already added to this TradingEngine",
            )

        self._event_feed_providers_by_type_dict[key] = provider
        logger.debug(f"Added event feed provider of class {key.__name__}")

    def remove_event_feed_provider(self, provider_type: type[EventFeedProvider]) -> None:
        """Remove an event feed provider by type.

        Args:
            provider_type: The provider class to remove.

        Raises:
            KeyError: If no provider of the given class exists.
        """
        # Check: provider type must be added before removing
        if provider_type not in self._event_feed_providers_by_type_dict:
            raise KeyError(
                f"Cannot call `remove_event_feed_provider` because $provider_type ('{provider_type.__name__}') is not added to this TradingEngine. Add the provider using `add_event_feed_provider` first.",
            )

        del self._event_feed_providers_by_type_dict[provider_type]
        logger.debug(f"Removed event feed provider of class {provider_type.__name__}")

    @property
    def event_feed_providers(self) -> dict[type[EventFeedProvider], EventFeedProvider]:
        """Get all event feed providers keyed by provider type.

        Returns:
            dict[type[EventFeedProvider], EventFeedProvider]: Mapping from provider class to instance.
        """
        return self._event_feed_providers_by_type_dict

    # endregion

    # region Brokers

    def add_broker(self, broker: Broker) -> None:
        """Add a broker (one per broker class).

        Args:
            broker: The broker instance to add.

        Raises:
            ValueError: If a broker of the same class was already added.
        """
        broker_type = type(broker)

        # Check: only one broker per concrete class
        if broker_type in self._brokers_by_type_dict:
            raise ValueError(f"Cannot call `add_broker` because a broker of class {broker_type.__name__} is already added to this TradingEngine")

        self._brokers_by_type_dict[broker_type] = broker
        broker.set_callbacks(self._route_broker_execution_to_strategy, self._route_broker_order_update_to_strategy)
        logger.debug(f"Broker (class {broker_type.__name__}) was added to {TradingEngine.__name__}.")

        # Register brokers that can consume PriceSample-s
        if isinstance(broker, PriceSampleConsumer):
            self._price_sample_consuming_brokers.append(broker)
            logger.debug(f"Broker (class {broker_type.__name__}) was added among brokers, that consume Event-s of type {PriceSampleSource.__name__}.")

    def remove_broker(self, broker_type: type[Broker]) -> None:
        """Remove a broker by type.

        Args:
            broker_type: The broker class to remove.

        Raises:
            KeyError: If no broker of the given class exists.
        """
        # Check: broker type must be added before removing
        if broker_type not in self._brokers_by_type_dict:
            raise KeyError(f"Cannot call `remove_broker` because $broker_type ('{broker_type.__name__}') is not added to this TradingEngine. Add the broker using `add_broker` first.")

        del self._brokers_by_type_dict[broker_type]
        logger.debug(f"Removed broker of class {broker_type.__name__}")

    @property
    def brokers(self) -> dict[type[Broker], Broker]:
        """Get all brokers keyed by broker type.

        Returns:
            dict[type[Broker], Broker]: Mapping from broker class to instance.
        """
        return self._brokers_by_type_dict

    # endregion

    # region Strategies

    def add_strategy(self, strategy: Strategy) -> None:
        """Add a Strategy to this TradingEngine using its required name.

        Strategy names must be unique within this TradingEngine. The engine enforces this: if another
        Strategy with the same name is already registered, this method raises ValueError.

        Args:
            strategy: The Strategy instance to add. Uses `strategy.name` as the key.

        Raises:
            ValueError: If a Strategy with the same name is already added, or if $strategy is not NEW.
        """
        name = strategy.name

        # Check: strategy name must be unique and not already added
        if name in self._strategies_by_name_bidict:
            raise ValueError(f"Cannot call `add_strategy` because Strategy named ('{name}') is already added to this TradingEngine. Choose a different name.")

        # Check: strategy must be NEW before attaching
        if strategy.state != StrategyState.NEW:
            raise ValueError(f"Cannot call `add_strategy` because $strategy is not NEW. Current $state is {strategy.state.name}. Provide a fresh instance of {strategy.__class__.__name__}.")

        # Connect strategy to this engine
        strategy.set_trading_engine(self)
        self._strategies_by_name_bidict[name] = strategy

        # Set up clocks tracking for this strategy
        self._clocks_by_strategy_dict[strategy] = StrategyClocks()

        # Set up EventFeed tracking for this strategy
        self._event_feeds_by_strategy_dict[strategy] = {}

        # Set up execution tracking for this strategy
        self._executions_by_strategy_name_dict[name] = []

        # Mark strategy as added
        strategy._state_machine.execute_action(StrategyAction.ADD_STRATEGY_TO_ENGINE)
        logger.debug(f"TradingEngine added Strategy named '{name}' (class {strategy.__class__.__name__})")

    def start_strategy(self, name: str) -> None:
        """Start a strategy with specified name.

        Args:
            name: Name of the strategy to start.

        Raises:
            KeyError: If no strategy with the given name exists.
            ValueError: If strategy is not in ADDED state.
        """
        # Check: strategy name must be added before starting
        if name not in self._strategies_by_name_bidict:
            raise KeyError(f"Cannot call `start_strategy` because strategy name $name ('{name}') is not added to this TradingEngine. Add the strategy using `add_strategy` first.")

        strategy = self._strategies_by_name_bidict[name]

        # Check: strategy must be able to start
        if not strategy._state_machine.can_execute_action(StrategyAction.START_STRATEGY):
            valid_actions = [a.value for a in strategy._state_machine.list_valid_actions()]
            raise ValueError(f"Cannot start strategy in state {strategy.state.name}. Valid actions: {valid_actions}")

        logger.info(f"Starting Strategy named '{name}' (class {strategy.__class__.__name__})")
        try:
            strategy.on_start()
            strategy._state_machine.execute_action(StrategyAction.START_STRATEGY)
            logger.debug(f"Strategy named '{name}' transitioned to {strategy.state.name}")
        except Exception as e:
            strategy._state_machine.execute_action(StrategyAction.ERROR_OCCURRED)
            logger.error(f"Error in `start_strategy` for Strategy named '{name}' (class {strategy.__class__.__name__}, state {strategy.state.name}): {e}")
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
        if name not in self._strategies_by_name_bidict:
            raise KeyError(f"Strategy named '{name}' is unknown.")

        strategy = self._strategies_by_name_bidict[name]

        # Check: strategy must be able to stop
        if not strategy._state_machine.can_execute_action(StrategyAction.STOP_STRATEGY):
            valid_actions = [a.value for a in strategy._state_machine.list_valid_actions()]
            raise ValueError(f"Cannot stop strategy in state {strategy.state.name}. Valid actions: {valid_actions}")

        logger.info(f"Stopping Strategy named '{name}'")

        try:
            strategy.on_stop()
            strategy._state_machine.execute_action(StrategyAction.STOP_STRATEGY)
            logger.debug(f"Strategy named '{name}' transitioned to {strategy.state.name}")
        except Exception as e:
            strategy._state_machine.execute_action(StrategyAction.ERROR_OCCURRED)
            logger.error(f"Strategy named '{name}' transitioned to {strategy.state.name} | Exception: {e}")
            raise

        # Cleanup all feeds
        self._close_and_remove_all_feeds_for_strategy(strategy)

    def remove_strategy(self, name: str) -> None:
        """Remove a strategy by name.

        Args:
            name: Name of the strategy to remove.

        Raises:
            KeyError: If no strategy with the given name exists.
            ValueError: If strategy is not in terminal state.
        """
        # Check: strategy name must be added before removing
        if name not in self._strategies_by_name_bidict:
            raise KeyError(f"Cannot call `remove_strategy` because strategy name $name ('{name}') is not added to this TradingEngine. Add the strategy using `add_strategy` first.")

        strategy = self._strategies_by_name_bidict[name]

        # Check: strategy must be in terminal state before removing
        if not strategy._state_machine.is_in_terminal_state():
            valid_actions = [a.value for a in strategy._state_machine.list_valid_actions()]
            raise ValueError(f"Cannot call `remove_strategy` because $state ({strategy.state.name}) is not terminal. Valid actions: {valid_actions}")

        # Remove clocks tracking for this strategy
        if strategy in self._clocks_by_strategy_dict:
            del self._clocks_by_strategy_dict[strategy]

        # Remove EventFeed tracking for this strategy
        del self._event_feeds_by_strategy_dict[strategy]

        # Remove execution tracking for this strategy
        if name in self._executions_by_strategy_name_dict:
            del self._executions_by_strategy_name_dict[name]

        # Remove from strategies' dictionary
        del self._strategies_by_name_bidict[name]

        # Detach engine reference from this strategy
        strategy._clear_trading_engine()
        logger.debug(f"Removed Strategy named '{name}' (class {strategy.__class__.__name__})")

    @property
    def strategies(self) -> bidict[str, Strategy]:
        """Get all strategies.

        Returns:
            Dictionary mapping strategy names to strategy instances.
        """
        return self._strategies_by_name_bidict

    def list_strategy_names(self) -> list[str]:
        """Returns names of all registered strategies.

        Returns:
            List of strategy names in registration order.
        """
        return list(self._strategies_by_name_bidict.keys())

    def list_executions_for_strategy(self, strategy_name: str) -> list[Execution]:
        """Returns all executions for the given Strategy.

        Args:
            strategy_name: Name of the Strategy to get executions for.

        Returns:
            List of Execution objects in chronological order.

        Raises:
            KeyError: If $strategy_name is not registered.
        """
        # Check: ensure $strategy_name exists
        if strategy_name not in self._executions_by_strategy_name_dict:
            raise KeyError(f"Cannot call `list_executions_for_strategy` because Strategy named '{strategy_name}' is not registered")

        return list(self._executions_by_strategy_name_dict[strategy_name])

    # endregion

    # region Lifecycle

    def start(self):
        """Start the engine and all your strategies.

        Connects in this order: EventFeedProvider(s) -> Brokers first -> then starts all strategies.
        """
        # Check: engine must be in NEW state before starting
        if not self._engine_state_machine.can_execute_action(EngineAction.START_ENGINE):
            valid_actions = [a.value for a in self._engine_state_machine.list_valid_actions()]
            raise ValueError(f"Cannot start engine in state {self.state.name}. Valid actions: {valid_actions}")

        logger.info(f"Starting TradingEngine: {len(self._event_feed_providers_by_type_dict)} event-feed-provider(s), {len(self._brokers_by_type_dict)} broker(s), {len(self._strategies_by_name_bidict)} strategy(ies)")

        try:
            # Connect event-feed-providers first
            for provider_type, provider in self._event_feed_providers_by_type_dict.items():
                provider.connect()
                logger.info(f"Connected event feed provider {provider_type.__name__}")

            # Connect brokers second
            for broker_type, broker in self._brokers_by_type_dict.items():
                broker.connect()
                logger.info(f"Connected broker {broker_type.__name__}")

            # Start strategies last
            started = 0
            for strategy_name in list(self._strategies_by_name_bidict.keys()):
                self.start_strategy(strategy_name)
                logger.info(f"Started Strategy named '{strategy_name}'")
                started += 1

            # Mark engine as running
            self._engine_state_machine.execute_action(EngineAction.START_ENGINE)
            logger.info(f"TradingEngine is RUNNING; started {started} strategy(ies)")

            # Start processing events
            self.run_event_processing_loop()
        except Exception:
            # Mark engine as failed
            self._engine_state_machine.execute_action(EngineAction.ERROR_OCCURRED)
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
            logger.debug("Skip `stop` because engine is already STOPPED")
            return

        # Check: engine must be in RUNNING state, when we want to stop it
        if not self._engine_state_machine.can_execute_action(EngineAction.STOP_ENGINE):
            valid_actions = [a.value for a in self._engine_state_machine.list_valid_actions()]
            raise ValueError(f"Cannot stop engine in state {self.state.name}. Valid actions: {valid_actions}")

        try:
            # Stop all strategies and clean up their event-feeds first
            stopped = 0
            for strategy_name, strategy in list(self._strategies_by_name_bidict.items()):
                if strategy._state_machine.can_execute_action(StrategyAction.STOP_STRATEGY):
                    self.stop_strategy(strategy_name)
                    logger.info(f"Stopped Strategy named '{strategy_name}'")
                    stopped += 1
                else:
                    logger.debug(f"Skip stopping Strategy named '{strategy_name}' in state {strategy.state.name}")

            # Disconnect brokers second
            disconnected_brokers = 0
            for broker_type, broker in self._brokers_by_type_dict.items():
                broker.disconnect()
                logger.info(f"Disconnected broker {broker_type.__name__}")
                disconnected_brokers += 1

            # Disconnect event-feed-providers last
            disconnected_providers = 0
            for provider_type, provider in self._event_feed_providers_by_type_dict.items():
                provider.disconnect()
                logger.info(f"Disconnected event-feed-provider {provider_type.__name__}")
                disconnected_providers += 1

            # Mark engine as stopped
            self._engine_state_machine.execute_action(EngineAction.STOP_ENGINE)
            logger.info(f"TradingEngine STOPPED; strategies stopped={stopped}, brokers disconnected={disconnected_brokers}, event-feed-providers disconnected={disconnected_providers}")
        except Exception:
            # Mark engine as failed
            self._engine_state_machine.execute_action(EngineAction.ERROR_OCCURRED)
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

        # While any active event-feeds exist, keep processing events
        while self._any_active_event_feeds_exist():
            # Go over all strategies in RUNNING state
            running_strategies = [s for s in self._strategies_by_name_bidict.values() if s.state == StrategyState.RUNNING]
            for strategy in running_strategies:
                strategy_name = self._get_strategy_name(strategy)

                # Find the oldest event and if found, then process it
                if (next_feed_tuple := self._find_feed_with_oldest_event(strategy)) is not None:
                    feed_name, feed, callback = next_feed_tuple
                    next_event = feed.pop()

                    # Update clocks for this strategy
                    self._clocks_by_strategy_dict[strategy].update_on_event(next_event.dt_event, next_event.dt_received)

                    # Process event in its callback
                    try:
                        callback(next_event)
                    except Exception as e:
                        logger.error(f"Exception raised during processing event: {next_event} for Strategy named '{strategy_name}'. | Exception: {e}")
                        # Move strategy to error state
                        strategy._state_machine.execute_action(StrategyAction.ERROR_OCCURRED)
                        # Allow strategy to handler error state (do some cleanup)
                        strategy.on_error(e)
                        # Cleanup all feeds for this strategy
                        self._close_and_remove_all_feeds_for_strategy(strategy)

                    # Route Events of type PriceSampleSource to all capable brokers
                    if isinstance(next_event, PriceSampleSource):
                        for sample in next_event.iter_price_samples():
                            for broker in self._price_sample_consuming_brokers:
                                broker.process_price_sample(sample)

                    # Notify EventFeed listeners after strategy callback.
                    # This is the single place listeners are invoked for EventFeed(s); feeds must not self-notify.
                    try:
                        for listener in feed.list_listeners():
                            try:
                                listener(next_event)
                            except Exception as le:
                                logger.error(f"Error in EventFeed listener for Strategy named '{strategy_name}' on EventFeed named '{feed_name}': {le}")
                    except Exception as outer:
                        logger.error(f"Error retrieving listeners for Strategy named '{strategy_name}' on EventFeed named '{feed_name}': {outer}")

            # Auto-stop strategies that have no active event-feeds left
            for name, strategy in list(self._strategies_by_name_bidict.items()):
                if strategy.state == StrategyState.RUNNING:
                    all_events_feeds_are_finished_for_strategy = not self._any_active_event_feeds_exist_for_strategy(strategy)
                    if all_events_feeds_are_finished_for_strategy:
                        try:
                            self.stop_strategy(name)
                            logger.info(f"Strategy named '{name}' was automatically stopped because all EventFeeds were finished")
                        except Exception as e:
                            logger.error(f"Error auto-stopping Strategy named '{name}': {e}")

        logger.info("Event processing loop completed - all EventFeeds finished")

        # Stop the engine when all data is processed
        self.stop()

    # endregion

    # region EventFeeds

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
        if strategy not in self._strategies_by_name_bidict.values():
            raise ValueError("Cannot call `add_event_feed_for_strategy` because $strategy ({strategy.__class__.__name__}) is not added to this TradingEngine. Add the strategy using `add_strategy` first.")

        # Check: feed_name must be unique per strategy
        event_feeds_by_name_dict = self._event_feeds_by_strategy_dict[strategy]
        if feed_name in event_feeds_by_name_dict:
            raise ValueError("Cannot call `add_event_feed_for_strategy` because event-feed with $feed_name ('{feed_name}') is already used for this strategy. Choose a different name.")

        # Timeline filtering if the strategy already processed events
        if strategy.last_event_time is not None:
            event_feed.remove_events_before(strategy.last_event_time)

        # Register locally
        event_feeds_by_name_dict[feed_name] = EventFeedCallbackPair(event_feed, callback)
        strategy_name = self._get_strategy_name(strategy)
        logger.info(f"Added EventFeed named '{feed_name}' to Strategy named '{strategy_name}'")

    def remove_event_feed_from_strategy(self, strategy: Strategy, feed_name: str) -> None:
        """Detach and close a feed by name for a strategy.

        Args:
            strategy: The strategy that owns the event-feed.
            feed_name: Name of the event-feed to remove.

        Raises:
            ValueError: If $strategy is not registered.
        """
        strategy_name = self._get_strategy_name(strategy)

        # Handle case where feed doesn't exist
        feed_callback_tuple = self._event_feeds_by_strategy_dict[strategy].get(feed_name, None)
        feed_does_not_exist = feed_callback_tuple is None
        if feed_does_not_exist:
            logger.warning(f"EventFeed named '{feed_name}' for Strategy named '{strategy_name}' cannot be removed, as there no such EventFeed.")
            return

        try:
            # Close the feed
            feed_to_close = feed_callback_tuple.feed
            feed_to_close.close()
        except Exception as e:
            # Just log error, there is no way how to fix this
            logger.error(f"Error happened while closing EventFeed named '{feed_name}' for Strategy named '{strategy_name}': {e}")

        # Remove EventFeed from strategy
        del self._event_feeds_by_strategy_dict[strategy][feed_name]
        logger.info(f"EventFeed named '{feed_name}' was removed from Strategy named '{strategy_name}'")

    # endregion

    # region Lookup utils

    def _get_strategy_name(self, strategy: Strategy) -> str:
        try:
            return self._strategies_by_name_bidict.inv[strategy]
        except KeyError:
            raise KeyError(f"Cannot call `_get_strategy_name` because $strategy (class {strategy.__class__.__name__}) is not registered in this TradingEngine")

    # endregion

    # region EventFeeds utils

    def _any_active_event_feeds_exist_for_strategy(self, strategy: Strategy):
        strategy_has_at_least_one_active_event_feed = any(not t.feed.is_finished() for t in self._event_feeds_by_strategy_dict.get(strategy, {}).values())
        return strategy_has_at_least_one_active_event_feed

    def _any_active_event_feeds_exist(self) -> bool:
        """Check if any event feeds across all strategies are still active (not finished)."""
        # Check each strategy's event feeds
        for strategy_event_feeds in self._event_feeds_by_strategy_dict.values():
            # Check each feed for this strategy
            for feed_entry in strategy_event_feeds.values():
                if not feed_entry.feed.is_finished():
                    return True
        return False

    def _find_feed_with_oldest_event(self, strategy: Strategy) -> tuple[str, EventFeed, Callable] | None:
        """
        Next returned event is always the oldest event from all this strategy's event-feeds.
        If more events have the same time `dt_event`, then event coming from first event-feed wins.

        :param strategy: specify strategy for which to find next event
        :return: tuple of (name, feed, callback), where
            name = name of event-feed
            feed = EventFeed containing the next event
            callback = callback function to process event
        """
        oldest_event: Event | None = None
        winner_tuple: tuple[str, EventFeed, Callable] | None = None

        # Find the next feed (name, feed, callback) with the oldest available event.
        for name, (feed, callback) in self._event_feeds_by_strategy_dict[strategy].items():
            event = feed.peek()
            if event is None:
                continue
            if oldest_event is None or event.dt_event < oldest_event.dt_event:
                # We found a new oldest event sourced from this feed.
                oldest_event = event
                winner_tuple = (name, feed, callback)

        return winner_tuple

    def _close_and_remove_all_feeds_for_strategy(self, strategy: Strategy) -> None:
        strategy_name = self._get_strategy_name(strategy)

        # Close all feeds for this Strategy
        event_feeds_by_name_dict = self._event_feeds_by_strategy_dict[strategy]
        for name, (feed, _) in list(event_feeds_by_name_dict.items()):
            try:
                feed.close()
            except Exception as e:
                logger.error(f"Error during closing EventFeed named '{name}' for Strategy named '{strategy_name}': {e}")

        # Remove all feeds for this Strategy
        event_feeds_by_name_dict.clear()

    # endregion

    # region Orders

    def submit_order(self, order: Order, broker: Broker, strategy: Strategy) -> None:
        """Send an order to your broker on behalf of $strategy.

        Args:
            order: The order to submit.
            broker: The broker to use.
            strategy: The Strategy submitting the order.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order is invalid or cannot be submitted, or if $order is re-owned.
        """
        # Check: do not remap an already submitted order to a different owner
        existing_route = self._routing_by_order_dict.get(order)
        if existing_route is not None and existing_route.strategy is not strategy:
            owner_name = self._get_strategy_name(existing_route.strategy)
            raise ValueError(f"Cannot call `submit_order` because Order $order_id ('{order.order_id}') is already owned by Strategy named '{owner_name}'")

        # Record routing: Strategy is origin (receives callbacks), Broker is executor
        self._routing_by_order_dict[order] = StrategyBrokerPair(strategy=strategy, broker=broker)
        # Delegate to broker
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

    def list_active_orders(self, broker: Broker) -> list[Order]:
        """Get all your active orders from a broker.

        Args:
            broker: The broker to get active orders from.

        Returns:
            List of all active orders for this broker.

        Raises:
            ConnectionError: If the broker is not connected.
        """
        return broker.list_active_orders()

    def get_routing_for_order(self, order: Order) -> StrategyBrokerPair:
        """Get routing information for an order.

        Returns the Strategy and Broker associated with $order. The Strategy is the origin
        that submitted the order and receives execution and order-state updates. The Broker
        is responsible for executing the order.

        Args:
            order: The order to get routing information for.
        """
        route: StrategyBrokerPair = self._routing_by_order_dict[order]
        return route

    # Broker → Engine callbacks (deterministic ordering ensured by Broker)
    def _route_broker_execution_to_strategy(self, execution: Execution) -> None:
        strategy, broker = self.get_routing_for_order(execution.order)

        try:
            strategy.on_execution(execution)
        except Exception as e:
            logger.error(f"Error in `Strategy.on_execution` for Strategy named '{strategy.name}': {e}")
            self._transition_strategy_to_error(strategy, e)

        # Store execution for later statistics
        self._executions_by_strategy_name_dict[strategy.name].append(execution)

    def _route_broker_order_update_to_strategy(self, order: Order) -> None:
        """Handle order state updates from broker.

        Called by broker when order changes state. Routes update to originating Strategy.
        Broker parameter removed; brokers now call with order only. Engine determines
        routing via `get_routing_for_order(order)`.
        """
        strategy, broker = self.get_routing_for_order(order)

        try:
            strategy.on_order_updated(order)
        except Exception as e:
            logger.error(f"Error in `Strategy.on_order_updated` for Strategy named '{strategy.name}': {e}")
            self._transition_strategy_to_error(strategy, e)
        finally:
            self._cleanup_if_terminal(order)

    def _transition_strategy_to_error(self, strategy: Strategy, exc: Exception) -> None:
        """Transition Strategy to ERROR and notify via `on_error`."""
        try:
            # Move strategy to ERROR state via state machine, if not already
            if strategy.state != StrategyState.ERROR:
                strategy._state_machine.execute_action(StrategyAction.ERROR_OCCURRED)
        finally:
            try:
                strategy.on_error(exc)
            except Exception as inner:
                logger.error(f"Error in `Strategy.on_error` for Strategy named '{strategy.name}': {inner}")

    # TODO: this is unfinished, needs some thinking, how to do it well
    def _cleanup_if_terminal(self, order: Order) -> None:
        """Remove $order mappings if it is in a terminal state.

        This placeholder will be implemented once `Order` exposes a state field.
        """
        # Example once states are available:
        # if getattr(order, "state", None) in {OrderState.FILLED, OrderState.CANCELLED, OrderState.REJECTED}:
        #     self._routing_by_order_dict.pop(order, None)
        return

    # endregion
