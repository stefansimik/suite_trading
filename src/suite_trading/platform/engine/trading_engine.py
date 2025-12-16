from __future__ import annotations
import logging
from datetime import datetime
from typing import Callable, NamedTuple, TYPE_CHECKING

from suite_trading.domain.event import Event
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.market_data.event_feed_provider import EventFeedProvider
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.broker.simulated_broker_protocol import SimulatedBroker
from suite_trading.domain.order.orders import Order
from suite_trading.domain.order.order_state import OrderStateCategory
from suite_trading.strategy.strategy_state_machine import StrategyState, StrategyAction
from suite_trading.platform.engine.engine_state_machine import EngineState, EngineAction, create_engine_state_machine
from bidict import bidict

from suite_trading.platform.engine.models.event_to_order_book.protocol import EventToOrderBookConverter
from suite_trading.platform.engine.models.event_to_order_book.default_impl import DefaultEventToOrderBookConverter

from suite_trading.utils.state_machine import StateMachine
from suite_trading.utils.datetime_tools import format_dt

if TYPE_CHECKING:
    from suite_trading.domain.order.execution import Execution


logger = logging.getLogger(__name__)

# region Helper classes


class StrategyBrokerPair(NamedTuple):
    """Pairs a Strategy with a Broker for order routing.

    Attributes:
        strategy: Strategy that owns the order and receives callbacks.
        broker: Broker that executes the order.
    """

    strategy: Strategy
    broker: Broker


class EventFeedRegistration(NamedTuple):
    """Internal registration record for a Strategy's EventFeed.

    Attributes:
        feed: The EventFeed instance managed by the engine.
        callback: Strategy callback that receives each Event from this feed.
        fill_event_filter: Callable that decides which Event(s) from this feed
            should drive simulated fills in simulated brokers
            Returns True to enable fill processing for the Event, False to skip it.
    """

    feed: EventFeed
    callback: Callable[[Event], None]
    fill_event_filter: Callable[[Event], bool]


# endregion


class TradingEngine:
    """Runs multiple trading strategies over a single shared timeline.

    TradingEngine owns Strategies, Brokers, and EventFeedProvider(s) and drives the
    main event-processing loop. All Strategies attached to one TradingEngine share
    a single simulated "now": at each step the engine picks the earliest available
    Event across all EventFeed(s) and delivers it to the owning Strategy.

    Individual Strategies may subscribe to different instruments or time ranges,
    and some may finish earlier than others, but they always advance through time
    in one global chronological order defined by `Event.dt_event` (and
    `Event.dt_received` for ties).
    """

    # region Init

    def __init__(self):
        """Create a new TradingEngine."""

        # Current state
        self._engine_state_machine: StateMachine = create_engine_state_machine()

        # Current simulated time on the engine-owned global timeline.
        self._current_engine_dt: datetime | None = None

        # Tracks timestamp of the last processed OrderBook
        self._last_processed_order_book_timestamp: datetime | None = None

        # Brokers
        self._brokers_by_name_bidict: bidict[str, Broker] = bidict()

        # Strategies
        self._strategies_by_name_bidict: bidict[str, Strategy] = bidict()

        # EventFeedProviders & EventFeeds
        self._event_feed_providers_by_name_bidict: bidict[str, EventFeedProvider] = bidict()
        self._event_feeds_by_strategy: dict[Strategy, dict[str, EventFeedRegistration]] = {}

        # Orders
        self._routing_by_order: dict[Order, StrategyBrokerPair] = {}

        # Executions
        self._executions_by_strategy: dict[Strategy, list[Execution]] = {}

        # MODELS (EVENT → ORDER BOOK)
        # Converter used to transform market‑data `Event`(s) into `OrderBook` snapshot(s)
        self._event_to_order_book_converter: EventToOrderBookConverter = DefaultEventToOrderBookConverter()

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

    # region Main

    def set_order_book_converter(self, converter: EventToOrderBookConverter) -> None:
        """Replace the Event→OrderBook converter used by the engine.

        This lets you customize how market‑data $event(s) are converted to OrderBook
        before they are sent to simulated brokers.

        Args:
            converter: Implementation of `EventToOrderBookConverter` to install.
        """
        self._event_to_order_book_converter = converter

    # endregion

    # region EventFeedProvider(s)

    def add_event_feed_provider(self, name: str, provider: EventFeedProvider) -> None:
        """Add an EventFeedProvider by name (one unique name per engine).

        Args:
            name: Unique provider name within this TradingEngine.
            provider: The EventFeedProvider instance to add.

        Raises:
            ValueError: If an EventFeedProvider with the same $name is already added.
        """
        # Precondition: provider name must be unique and not already added
        if name in self._event_feed_providers_by_name_bidict:
            raise ValueError(f"Cannot call `add_event_feed_provider` because EventFeedProvider named ('{name}') is already added to this TradingEngine. Choose a different name.")

        self._event_feed_providers_by_name_bidict[name] = provider
        logger.debug(f"TradingEngine added EventFeedProvider named '{name}' (class {provider.__class__.__name__})")

    def remove_event_feed_provider(self, name: str) -> None:
        """Remove an EventFeedProvider by name.

        Args:
            name: The provider name to remove.

        Raises:
            KeyError: If no EventFeedProvider with the given $name exists.
        """
        # Precondition: provider name must be added before removing
        if name not in self._event_feed_providers_by_name_bidict:
            raise KeyError(f"Cannot call `remove_event_feed_provider` because provider name $name ('{name}') is not added to this TradingEngine. Add the provider using `add_event_feed_provider` first.")

        del self._event_feed_providers_by_name_bidict[name]
        logger.debug(f"Removed EventFeedProvider named '{name}'")

    @property
    def event_feed_providers(self) -> bidict[str, EventFeedProvider]:
        """Get all EventFeedProvider(s) keyed by name.

        Returns:
            bidict[str, EventFeedProvider]: Bi-directional mapping from provider name to instance.
        """
        return self._event_feed_providers_by_name_bidict

    def list_event_feed_provider_names(self) -> list[str]:
        """List names of all registered EventFeedProvider(s) in registration order."""
        return list(self._event_feed_providers_by_name_bidict.keys())

    # endregion

    # region Brokers

    def add_broker(self, name: str, broker: Broker) -> None:
        """Add a Broker by name (one unique name per engine).

        Each registered Broker instance represents a **separate trading account**.
        To model multiple accounts, register multiple Broker instances under
        different names, for example ``"sim_portfolio"``, ``"sim_A"``,
        ``"sim_B"``. Strategies choose which account they trade by passing a
        specific Broker instance to `Strategy.submit_order`.

        Typical patterns:

        - Single-account portfolio: one shared Broker (for example a
          `SimBroker`) used by many Strategy(ies).
        - Per-strategy simulations: multiple `SimBroker` instances registered
          under different names; each Strategy uses its own instance.

        Args:
            name: Unique broker name within this TradingEngine.
            broker: The Broker instance to add (one logical account).

        Raises:
            ValueError: If a Broker with the same $name is already added.
        """
        # Precondition: broker name must be unique and not already added
        if name in self._brokers_by_name_bidict:
            raise ValueError(f"Cannot call `add_broker` because Broker named ('{name}') is already added to this TradingEngine. Choose a different name.")

        self._brokers_by_name_bidict[name] = broker
        broker.set_callbacks(self._route_broker_execution_to_strategy, self._route_broker_order_update_to_strategy)
        logger.debug(f"TradingEngine added Broker named '{name}' (class {broker.__class__.__name__})")

        # No special registration for price-sample processing; capability is checked at use-site

    def remove_broker(self, name: str) -> None:
        """Remove a Broker by name.

        Args:
            name: The broker name to remove.

        Raises:
            KeyError: If no Broker with the given $name exists.
        """
        # Precondition: broker name must be added before removing
        if name not in self._brokers_by_name_bidict:
            raise KeyError(f"Cannot call `remove_broker` because broker name $name ('{name}') is not added to this TradingEngine. Add the broker using `add_broker` first.")

        del self._brokers_by_name_bidict[name]
        logger.debug(f"Removed Broker named '{name}'")

    @property
    def brokers(self) -> bidict[str, Broker]:
        """Get all Brokers keyed by name.

        The returned bi-directional mapping exposes the engine's Broker
        registry:

        - Keys are broker names as passed to `add_broker`.
        - Values are Broker instances, each representing one logical account.

        This mapping is intended for inspection and advanced wiring. Most
        strategies should receive concrete Broker instances via configuration
        (for example, constructor arguments) rather than relying on global
        lookups.

        Returns:
            bidict[str, Broker]: Bi-directional mapping from broker name to instance.
        """
        return self._brokers_by_name_bidict

    def list_broker_names(self) -> list[str]:
        """List names of all registered Brokers in registration order.

        Each name identifies one Broker instance and therefore one trading
        account registered in this TradingEngine.
        """
        return list(self._brokers_by_name_bidict.keys())

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

        # Precondition: strategy name must be unique and not already added
        if name in self._strategies_by_name_bidict:
            raise ValueError(f"Cannot call `add_strategy` because Strategy named ('{name}') is already added to this TradingEngine. Choose a different name.")

        # Precondition: strategy must be NEW before attaching
        if strategy.state != StrategyState.NEW:
            raise ValueError(f"Cannot call `add_strategy` because $strategy is not NEW. Current $state is {strategy.state.name}. Provide a fresh instance of {strategy.__class__.__name__}.")

        # Connect strategy to this engine
        strategy.set_trading_engine(self)
        self._strategies_by_name_bidict[name] = strategy

        # Set up EventFeed tracking for this strategy
        self._event_feeds_by_strategy[strategy] = {}

        # Set up execution tracking for this strategy (keyed by Strategy instance)
        self._executions_by_strategy[strategy] = []

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
        # Precondition: strategy name must be added before starting
        if name not in self._strategies_by_name_bidict:
            raise KeyError(f"Cannot call `start_strategy` because strategy name $name ('{name}') is not added to this TradingEngine. Add the strategy using `add_strategy` first.")

        strategy = self._strategies_by_name_bidict[name]

        # Precondition: strategy must be able to start
        if not strategy._state_machine.can_execute_action(StrategyAction.START_STRATEGY):
            valid_actions = [a.value for a in strategy._state_machine.list_valid_actions()]
            raise ValueError(f"Cannot start strategy in state {strategy.state.name}. Valid actions: {valid_actions}")

        logger.info(f"Starting Strategy named '{name}' (class {strategy.__class__.__name__})")
        try:
            strategy.on_start()
            strategy._state_machine.execute_action(StrategyAction.START_STRATEGY)
            logger.debug(f"Strategy named '{name}' (class {strategy.__class__.__name__}) transitioned to {strategy.state.name}")
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
        # Precondition: strategy name must be added before stopping
        if name not in self._strategies_by_name_bidict:
            raise KeyError(f"Strategy named '{name}' is unknown.")

        strategy = self._strategies_by_name_bidict[name]

        # Precondition: strategy must be able to stop
        if not strategy._state_machine.can_execute_action(StrategyAction.STOP_STRATEGY):
            valid_actions = [a.value for a in strategy._state_machine.list_valid_actions()]
            raise ValueError(f"Cannot stop strategy in state {strategy.state.name}. Valid actions: {valid_actions}")

        logger.info(f"Stopping Strategy named '{name}' (class {strategy.__class__.__name__})")

        try:
            strategy.on_stop()
            strategy._state_machine.execute_action(StrategyAction.STOP_STRATEGY)
            logger.debug(f"Strategy named '{name}' (class {strategy.__class__.__name__}) transitioned to {strategy.state.name}")
        except Exception as e:
            strategy._state_machine.execute_action(StrategyAction.ERROR_OCCURRED)
            logger.error(f"Error in `stop_strategy` for Strategy named '{name}' (class {strategy.__class__.__name__}, state {strategy.state.name}): {e}")
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
        # Precondition: strategy name must be added before removing
        if name not in self._strategies_by_name_bidict:
            raise KeyError(f"Cannot call `remove_strategy` because strategy name $name ('{name}') is not added to this TradingEngine. Add the strategy using `add_strategy` first.")

        strategy = self._strategies_by_name_bidict[name]

        # Precondition: strategy must be in terminal state before removing
        if not strategy._state_machine.is_in_terminal_state():
            valid_actions = [a.value for a in strategy._state_machine.list_valid_actions()]
            raise ValueError(f"Cannot call `remove_strategy` because $state ({strategy.state.name}) is not terminal. Valid actions: {valid_actions}")

        # Remove EventFeed tracking for this strategy
        del self._event_feeds_by_strategy[strategy]

        # Remove execution tracking for this strategy
        if strategy in self._executions_by_strategy:
            del self._executions_by_strategy[strategy]

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
        """Return all executions for Strategy named $strategy_name.

        Args:
            strategy_name: Name of the Strategy to get executions for.

        Returns:
            List of Execution objects in chronological order.

        Raises:
            KeyError: If $strategy_name is not registered in this TradingEngine.
        """
        # Precondition: ensure $strategy_name exists in this TradingEngine
        if strategy_name not in self._strategies_by_name_bidict:
            raise KeyError(f"Cannot call `list_executions_for_strategy` because Strategy named '{strategy_name}' is not registered in this TradingEngine")

        strategy = self._strategies_by_name_bidict[strategy_name]
        return list(self._executions_by_strategy.get(strategy, []))

    # endregion

    # region Lifecycle

    def start(self):
        """Start the engine and all your strategies.

        Connects in this order: EventFeedProvider(s) -> Brokers first -> then starts all strategies.
        """
        # Precondition: engine must be in NEW state before starting
        if not self._engine_state_machine.can_execute_action(EngineAction.START_ENGINE):
            valid_actions = [a.value for a in self._engine_state_machine.list_valid_actions()]
            raise ValueError(f"Cannot start engine in state {self.state.name}. Valid actions: {valid_actions}")

        logger.info(f"Starting TradingEngine: {len(self._event_feed_providers_by_name_bidict)} event-feed-provider(s), {len(self._brokers_by_name_bidict)} broker(s), {len(self._strategies_by_name_bidict)} strategy(ies)")

        try:
            # Connect event-feed-providers first
            for provider_name, provider in self._event_feed_providers_by_name_bidict.items():
                provider.connect()
                logger.info(f"Connected EventFeedProvider named '{provider_name}' (class {provider.__class__.__name__})")

            # Connect brokers second
            for broker_name, broker in self._brokers_by_name_bidict.items():
                broker.connect()
                logger.info(f"Connected Broker named '{broker_name}' (class {broker.__class__.__name__})")

            # Start strategies last
            started = 0
            for strategy_name, strategy in list(self._strategies_by_name_bidict.items()):
                self.start_strategy(strategy_name)
                logger.info(f"Started Strategy named '{strategy_name}' (class {strategy.__class__.__name__})")
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

        # Precondition: engine must be in RUNNING state, when we want to stop it
        if not self._engine_state_machine.can_execute_action(EngineAction.STOP_ENGINE):
            valid_actions = [a.value for a in self._engine_state_machine.list_valid_actions()]
            raise ValueError(f"Cannot stop engine in state {self.state.name}. Valid actions: {valid_actions}")

        try:
            # Firsr: Stop all strategies and clean up their event-feeds
            stopped = 0
            for strategy_name, strategy in list(self._strategies_by_name_bidict.items()):
                if strategy._state_machine.can_execute_action(StrategyAction.STOP_STRATEGY):
                    self.stop_strategy(strategy_name)
                    logger.info(f"Stopped Strategy named '{strategy_name}' (class {strategy.__class__.__name__})")
                    stopped += 1

            # Second: Disconnect brokers
            disconnected_brokers = 0
            for broker_name, broker in self._brokers_by_name_bidict.items():
                broker.disconnect()
                logger.info(f"Disconnected Broker named '{broker_name}' (class {broker.__class__.__name__})")
                disconnected_brokers += 1

            # Last: Disconnect event-feed-providers
            disconnected_providers = 0
            for provider_name, provider in self._event_feed_providers_by_name_bidict.items():
                provider.disconnect()
                logger.info(f"Disconnected EventFeedProvider named '{provider_name}' (class {provider.__class__.__name__})")
                disconnected_providers += 1

            # Mark engine as stopped
            self._engine_state_machine.execute_action(EngineAction.STOP_ENGINE)
            logger.info(f"TradingEngine STOPPED; strategies stopped={stopped}, brokers disconnected={disconnected_brokers}, event-feed-providers disconnected={disconnected_providers}")
        except Exception:
            # Mark engine as failed
            self._engine_state_machine.execute_action(EngineAction.ERROR_OCCURRED)
            raise

    def run_event_processing_loop(self) -> None:
        """Process events in global chronological order until all feeds finish.

        How it works:
        - Considers all EventFeed(s) across all RUNNING strategies.
        - At each step, finds the earliest available Event using the Event ordering
          (`dt_event`, then `dt_received`).
        - Pops that Event from its feed, routes any derived OrderBook to
          simulated brokers, then delivers the Event to the
          owning Strategy via its callback.
        - Repeats until all EventFeed(s) report finished.

        Some EventFeed(s) may be configured via `use_for_simulated_fills` to drive
         fills in simulated brokers . The engine
        applies a per-feed `fill_event_filter` to each Event before converting it
        to OrderBook snapshot(s) for brokers.

        The engine stops automatically when all EventFeed(s) for all strategies are
        finished.

        Raises:
            ValueError: If engine is not in RUNNING state.
        """
        # Precondition: engine must be in RUNNING state
        if self.state != EngineState.RUNNING:
            raise ValueError(f"Cannot run processing loop because engine is not RUNNING. Current state: {self.state.name}")

        logger.info("Starting event processing loop")

        # While any active event-feeds exist, keep processing events in global time order
        while self._any_active_event_feeds_exist():
            # Find the next event feed
            event_feed_tuple = self._find_event_feed_with_earliest_event()

            # If no Event is currently available across active feeds, we just continue.
            if event_feed_tuple is None:
                logger.debug("No next Event available across active EventFeed(s); breaking event processing loop early")
                continue

            # We have Event to process; Unpack the selected feed tuple and pull the next Event to process
            strategy, event_feed_name, event_feed, callback = event_feed_tuple
            strategy_name = self._get_strategy_name(strategy)
            current_event = event_feed.pop()
            current_event_dt = current_event.dt_event

            # Set current time on global engine timeline
            self._current_engine_dt = current_event_dt

            # Decide if this Event should drive  fills in simulated brokers
            event_feed_registration = self._event_feeds_by_strategy[strategy][event_feed_name]
            event_should_drive_simulated_fills = event_feed_registration.fill_event_filter(current_event)

            simulated_brokers = self._list_simulated_brokers()
            if simulated_brokers and event_should_drive_simulated_fills and self._event_to_order_book_converter.can_convert(current_event):
                order_books = self._event_to_order_book_converter.convert_to_order_books(current_event)
                for order_book in order_books:
                    # Check: ignore stale OrderBook snapshots (defensive)
                    if (self._last_processed_order_book_timestamp is not None) and (order_book.timestamp < self._last_processed_order_book_timestamp):
                        logger.debug(f"Skipped OrderBook with timestamp {format_dt(order_book.timestamp)} for Strategy named '{strategy_name}' (class {strategy.__class__.__name__}) - older than last processed OrderBook timestamp {format_dt(self._last_processed_order_book_timestamp)}")
                        continue

                    # Process OrderBook with valid timestamp
                    logger.debug(f"Processing OrderBook with timestamp {format_dt(order_book.timestamp)} for Strategy named '{strategy_name}' (class {strategy.__class__.__name__})")

                    # Route to simulated brokers for order-price matching
                    for broker in simulated_brokers:
                        broker.set_current_dt(order_book.timestamp)  # Move broker's time by OrderBook
                        broker.process_order_book(order_book)

                    should_update_last_processed_order_book_timestamp = self._last_processed_order_book_timestamp is None or order_book.timestamp > self._last_processed_order_book_timestamp
                    if should_update_last_processed_order_book_timestamp:
                        self._last_processed_order_book_timestamp = order_book.timestamp

            # Set broker time to Event time
            for broker in simulated_brokers:
                broker.set_current_dt(current_event_dt)

            # Process event in its callback (deliver to Strategy)
            try:
                callback(current_event)
            except Exception as e:
                logger.error(f"Error processing {current_event} for Strategy named '{strategy_name}' (class {strategy.__class__.__name__}): {e}")
                # Move strategy to error state
                strategy._state_machine.execute_action(StrategyAction.ERROR_OCCURRED)
                # Allow strategy to handle error state (do some cleanup)
                strategy.on_error(e)
                # Cleanup all feeds for this strategy
                self._close_and_remove_all_feeds_for_strategy(strategy)

            # Notify EventFeed listeners after strategy callback.
            # This is the single place listeners are invoked for EventFeed(s); feeds must not self-notify.
            try:
                for listener in event_feed.list_listeners():
                    try:
                        listener(current_event)
                    except Exception as le:
                        logger.error(f"Error in EventFeed listener for Strategy named '{strategy_name}' (class {strategy.__class__.__name__}) on EventFeed named '{event_feed_name}': {le}")
            except Exception as outer:
                logger.error(f"Error retrieving listeners for Strategy named '{strategy_name}' (class {strategy.__class__.__name__}) on EventFeed named '{event_feed_name}': {outer}")

            # Auto-stop strategies that have no active event-feeds left
            for name, strategy in list(self._strategies_by_name_bidict.items()):
                if strategy.state == StrategyState.RUNNING:
                    all_events_feeds_are_finished_for_strategy = not self._any_active_event_feeds_exist_for_strategy(strategy)
                    if all_events_feeds_are_finished_for_strategy:
                        try:
                            self.stop_strategy(name)
                            logger.info(f"Strategy named '{name}' (class {strategy.__class__.__name__}) was automatically stopped because all EventFeeds were finished")
                        except Exception as e:
                            logger.error(f"Error auto-stopping Strategy named '{name}' (class {strategy.__class__.__name__}): {e}")

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
        *,
        use_for_simulated_fills: bool | Callable[[Event], bool] = False,
    ) -> None:
        """Attach an EventFeed to a Strategy and register metadata.

        The engine owns the global simulated timeline for all strategies. When you add a
        new EventFeed while the engine is already RUNNING and has processed events, the
        engine calls `EventFeed.remove_events_before` with the current global
        `Event.dt_event` before registering the feed. This ensures that the new feed does
        not emit events that are "in the past" relative to other feeds and keeps the
        overall event stream in non-decreasing time order.

        Args:
            strategy: The Strategy that will receive events.
            feed_name: Unique name for this EventFeed within the Strategy.
            event_feed: The EventFeed instance to manage.
            callback: Function to call when events are received.
            use_for_simulated_fills: Controls if and how this EventFeed is used to
                drive simulated fills in simulated brokers.
                Use False (default) to never drive simulated fills, True to use all
                events, or provide a Callable[[Event], bool] that returns True only
                for Event(s) that should drive simulated fills.

        Raises:
            ValueError: If $strategy is not added to this TradingEngine or $feed_name is duplicate.
        """
        # Precondition: strategy must be added to this engine
        if strategy not in self._strategies_by_name_bidict.values():
            raise ValueError("Cannot call `add_event_feed_for_strategy` because $strategy ({strategy.__class__.__name__}) is not added to this TradingEngine. Add the strategy using `add_strategy` first.")

        # Precondition: feed_name must be unique per strategy
        event_feeds_by_name_dict = self._event_feeds_by_strategy[strategy]
        if feed_name in event_feeds_by_name_dict:
            raise ValueError("Cannot call `add_event_feed_for_strategy` because event-feed with $feed_name ('{feed_name}') is already used for this strategy. Choose a different name.")

        def _block_all_events_for_simulated_fills(_event: Event) -> bool:
            return False

        def _pass_all_events_for_simulated_fills(_event: Event) -> bool:
            return True

        # Normalize $use_for_simulated_fills to a callable so the event loop always works with a simple bool decision per Event
        if use_for_simulated_fills is False:
            fill_event_filter = _block_all_events_for_simulated_fills
        elif use_for_simulated_fills is True:
            fill_event_filter = _pass_all_events_for_simulated_fills
        else:
            fill_event_filter = use_for_simulated_fills

        # Timeline filtering if the engine already processed events (shared global time)
        last_event_time = self._current_engine_dt
        if last_event_time is not None:
            event_feed.remove_events_before(last_event_time)

        # Register locally
        registration = EventFeedRegistration(feed=event_feed, callback=callback, fill_event_filter=fill_event_filter)
        event_feeds_by_name_dict[feed_name] = registration
        strategy_name = self._get_strategy_name(strategy)
        logger.info(f"Added EventFeed named '{feed_name}' to Strategy named '{strategy_name}' (class {strategy.__class__.__name__})")

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
        registration = self._event_feeds_by_strategy[strategy].get(feed_name)
        feed_does_not_exist = registration is None
        if feed_does_not_exist:
            logger.warning(f"EventFeed named '{feed_name}' for Strategy named '{strategy_name}' (class {strategy.__class__.__name__}) cannot be removed, as there is no such EventFeed")
            return

        try:
            # Close the feed
            feed_to_close = registration.feed
            feed_to_close.close()
        except Exception as e:
            # Just log error, there is no way how to fix this
            logger.error(f"Error closing EventFeed named '{feed_name}' for Strategy named '{strategy_name}' (class {strategy.__class__.__name__}): {e}")

        # Remove EventFeed from strategy
        del self._event_feeds_by_strategy[strategy][feed_name]
        logger.info(f"EventFeed named '{feed_name}' was removed from Strategy named '{strategy_name}' (class {strategy.__class__.__name__})")

    # endregion

    # region Lookup utils

    def _get_strategy_name(self, strategy: Strategy) -> str:
        try:
            return self._strategies_by_name_bidict.inv[strategy]
        except KeyError:
            raise KeyError(f"Cannot call `_get_strategy_name` because $strategy (class {strategy.__class__.__name__}) is not registered in this TradingEngine")

    def _get_broker_name(self, broker: Broker) -> str:
        try:
            return self._brokers_by_name_bidict.inv[broker]
        except KeyError:
            raise KeyError(f"Cannot call `_get_broker_name` because $broker (class {broker.__class__.__name__}) is not registered in this TradingEngine")

    def _get_event_feed_provider_name(self, provider: EventFeedProvider) -> str:
        try:
            return self._event_feed_providers_by_name_bidict.inv[provider]
        except KeyError:
            raise KeyError(f"Cannot call `_get_event_feed_provider_name` because $provider (class {provider.__class__.__name__}) is not registered in this TradingEngine")

    def _list_simulated_brokers(self) -> list[SimulatedBroker]:
        """Return list of all simulated brokers

        Returns:
            list[SimulatedBroker]: list of simulated Brokers that require OrderBook snapshots
            to drive simulated order-price matching and fills.
        """
        return [broker for broker in self._brokers_by_name_bidict.values() if isinstance(broker, SimulatedBroker)]

    # endregion

    # region EventFeeds utils

    def _any_active_event_feeds_exist_for_strategy(self, strategy: Strategy):
        strategy_has_at_least_one_active_event_feed = any(not t.feed.is_finished() for t in self._event_feeds_by_strategy.get(strategy, {}).values())
        return strategy_has_at_least_one_active_event_feed

    def _any_active_event_feeds_exist(self) -> bool:
        """Check if any event feeds across all strategies are still active (not finished)."""
        # Check each strategy's event feeds
        for strategy_event_feeds in self._event_feeds_by_strategy.values():
            # Check each feed for this strategy
            for feed_entry in strategy_event_feeds.values():
                if not feed_entry.feed.is_finished():
                    return True
        return False

    def _find_event_feed_with_earliest_event(self) -> tuple[Strategy, str, EventFeed, Callable[[Event], None]] | None:
        """Return the next (Strategy, feed, callback) pair with the globally earliest Event.

        This scans all EventFeed(s) for strategies currently known to the engine and
        selects the earliest available Event using the Event ordering (`dt_event`,
        then `dt_received`). Strategies that are not in RUNNING state are ignored.

        Returns:
            tuple[Strategy, str, EventFeed, Callable[[Event], None]] | None: The owning
            Strategy, feed name, EventFeed, and callback for the earliest Event, or None
            if no Event is currently available across active feeds.
        """
        oldest_event: Event | None = None
        result: tuple[Strategy, str, EventFeed, Callable[[Event], None]] | None = None

        for strategy, event_feeds_by_name_dict in self._event_feeds_by_strategy.items():
            if strategy.state != StrategyState.RUNNING:
                continue

            for event_feed_name, registration in event_feeds_by_name_dict.items():
                event_feed = registration.feed
                callback = registration.callback
                peeked_event = event_feed.peek()
                if peeked_event is None:
                    continue

                if oldest_event is None or peeked_event < oldest_event:
                    oldest_event = peeked_event
                    result = (strategy, event_feed_name, event_feed, callback)

        return result

    def _close_and_remove_all_feeds_for_strategy(self, strategy: Strategy) -> None:
        strategy_name = self._get_strategy_name(strategy)

        # Close all feeds for this Strategy
        event_feeds_by_name_dict = self._event_feeds_by_strategy[strategy]
        for name, registration in list(event_feeds_by_name_dict.items()):
            try:
                feed = registration.feed
                feed.close()
            except Exception as e:
                logger.error(f"Error closing EventFeed named '{name}' for Strategy named '{strategy_name}' (class {strategy.__class__.__name__}): {e}")

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
        # Precondition: do not remap an already submitted order to a different owner
        existing_route = self._routing_by_order.get(order)
        if existing_route is not None and existing_route.strategy is not strategy:
            owner_name = self._get_strategy_name(existing_route.strategy)
            raise ValueError(f"Cannot call `submit_order` because Order $id ('{order.id}') is already owned by Strategy named '{owner_name}'")

        # Record routing: Strategy is origin (receives callbacks), Broker is executor
        self._routing_by_order[order] = StrategyBrokerPair(strategy=strategy, broker=broker)
        # Delegate to broker
        broker.submit_order(order)

    def cancel_order(self, order: Order) -> None:
        """Cancel an order with your broker.

        Args:
            order: The order to cancel.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order cannot be cancelled.
            KeyError: If $order was not submitted through this TradingEngine.
        """
        # Precondition: order must have been submitted through this engine
        if order not in self._routing_by_order:
            raise KeyError(f"Cannot call `cancel_order` because $order (id '{order.id}') was not submitted through this TradingEngine")

        strategy, broker = self.get_routing_for_order(order)
        broker.cancel_order(order)

    def modify_order(self, order: Order) -> None:
        """Change an order with your broker.

        Args:
            order: The order to modify with updated parameters.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order cannot be modified.
            KeyError: If $order was not submitted through this TradingEngine.
        """
        # Precondition: order must have been submitted through this engine
        if order not in self._routing_by_order:
            raise KeyError(f"Cannot call `modify_order` because $order (id '{order.id}') was not submitted through this TradingEngine")

        strategy, broker = self.get_routing_for_order(order)
        broker.modify_order(order)

    def get_routing_for_order(self, order: Order) -> StrategyBrokerPair:
        """Get routing information for an order.

        Returns the Strategy and Broker associated with $order. The Strategy is the origin
        that submitted the order and receives execution and order-state updates. The Broker
        is responsible for executing the order.

        Args:
            order: The order to get routing information for.
        """
        route: StrategyBrokerPair = self._routing_by_order[order]
        return route

    # Broker → Engine callbacks (deterministic ordering ensured by Broker)
    def _route_broker_execution_to_strategy(self, execution: Execution) -> None:
        strategy, broker = self.get_routing_for_order(execution.order)

        try:
            strategy.on_execution(execution)
        except Exception as e:
            logger.error(f"Error in `Strategy.on_execution` for Strategy named '{strategy.name}' (class {strategy.__class__.__name__}): {e}")
            self._transition_strategy_to_error(strategy, e)

        # Store execution for later statistics
        self._executions_by_strategy[strategy].append(execution)

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
            logger.error(f"Error in `Strategy.on_order_updated` for Strategy named '{strategy.name}' (class {strategy.__class__.__name__}): {e}")
            self._transition_strategy_to_error(strategy, e)

        # CLEANUP: If order is terminal, remove routing info
        if order.state_category == OrderStateCategory.TERMINAL:
            self._routing_by_order.pop(order, None)

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
                logger.error(f"Error in `Strategy.on_error` for Strategy named '{strategy.name}' (class {strategy.__class__.__name__}): {inner}")

    # endregion
