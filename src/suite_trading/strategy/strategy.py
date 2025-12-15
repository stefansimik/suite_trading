from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable
from suite_trading.domain.event import Event
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy_state_machine import StrategyState, StrategyAction, create_strategy_state_machine

if TYPE_CHECKING:
    from suite_trading.platform.engine.trading_engine import TradingEngine
    from suite_trading.domain.order.execution import Execution

logger = logging.getLogger(__name__)


class Strategy(ABC):
    """Base class for all trading strategies executed by a TradingEngine.

    **Shared engine timeline:**
    All Strategy instances attached to the same `TradingEngine` share a single simulated
    timeline. The engine is responsible for scheduling events in global chronological
    order; a Strategy never advances its own time.

    Timeline model:

    - There is one engine "now" defined by the last processed `Event.dt_event`.
    - Different strategies may subscribe to different instruments or date ranges, but
      events are always delivered in non-decreasing event time across the whole engine.
    - Account isolation is achieved via Broker instances (one Broker instance = one
      account), not via separate per-strategy timelines.

    Strategies focus on reacting to events and submitting orders. They should not try to
    re-order events or manage their own notion of time; the `TradingEngine` guarantees
    correct global ordering across all strategies and EventFeed(s).
    """

    # region Init

    def __init__(self, name: str) -> None:
        """Initialize a new Strategy with a required user-facing name.

        Note:
            The $name must be unique among all Strategy(ies) added to the same TradingEngine.
            The engine enforces this constraint in `TradingEngine.add_strategy` and raises
            ValueError on duplicates.

        Args:
            name (str): Required name for this Strategy. Must be non-empty.

        Raises:
            TypeError: If $name is not a str.
            ValueError: If $name is empty or whitespace only.
        """
        # Check: validate $name is a non-empty str
        if not isinstance(name, str):
            raise TypeError(f"Strategy could not be instantiated because $name must be a str (got type '{type(name).__name__}') in `Strategy.__init__`.")
        if name.strip() == "":
            raise ValueError("Strategy could not be instantiated because $name cannot be empty or whitespace in `Strategy.__init__`.")

        self._name = name
        self._trading_engine = None
        self._state_machine = create_strategy_state_machine()

    # endregion

    # region Attach engine

    def set_trading_engine(self, trading_engine: TradingEngine) -> None:
        """
        Attaches the TradingEngine so this Strategy can interact with platform features.

        Raises:
            RuntimeError: If $_trading_engine is already set or $state of Strategy is not NEW.
        """
        # Check: if TradingEngine is not already set in this Strategy - because we want to set it now
        if self._trading_engine is not None:
            raise RuntimeError(
                "Cannot call `_set_trading_engine` because $_trading_engine is already set.",
            )

        # Check: Strategy must be in $state NEW, when we want to set TradingEngine to this Strategy
        if self.state != StrategyState.NEW:
            raise RuntimeError(
                (f"Cannot call `_set_trading_engine` because $state ({self.state.name}) is not NEW. Provide a fresh instance."),
            )

        # Set TradingEngine to this Strategy
        self._trading_engine = trading_engine

    def _clear_trading_engine(self) -> None:
        """Detach the trading engine reference.

        Raises:
            RuntimeError: If $_trading_engine is None.
        """
        _ = self._require_trading_engine()

        self._trading_engine = None

    # endregion

    # region Internal

    def _require_trading_engine(self) -> TradingEngine:
        """Return the attached TradingEngine or raise if missing.

        Notes:
         - TradingEngine manages Strategies - not vice versa. We should prefer Strategy APIs over direct engine calls if possible.
         - TradingEngine should be used for advanced use-cases only, when you know, what you're doing.

         Returns:
             TradingEngine: The attached TradingEngine.

         Raises:
             RuntimeError: If $_trading_engine is None
        """
        # Check: TradingEngine must be attached to this Strategy
        if self._trading_engine is None:
            raise RuntimeError("Cannot proceed because $_trading_engine is None. Add the Strategy to a TradingEngine using `add_strategy` first.")
        return self._trading_engine

    # endregion

    # region Name & State

    @property
    def name(self) -> str:
        """Get the required name of this Strategy."""
        return self._name

    @property
    def state(self) -> StrategyState:
        """Get current lifecycle state.

        Returns:
            StrategyState: Current lifecycle state of this strategy.
        """
        return self._state_machine.current_state

    # endregion

    # region Lifecycle hooks

    def on_start(self):
        """Called when the strategy is started.

        This method should be overridden by subclasses to implement
        initialization logic when the strategy starts.
        """
        logger.debug(f"{self.__class__.__name__} default `on_start` called in state {self.state.name}")

    def on_stop(self):
        """Called when the strategy is stopped.

        This method should be overridden by subclasses to implement
        cleanup logic when the strategy stops.

        Note: All infrastructure cleanup (event feeds, subscriptions) is handled
        automatically by TradingEngine. All event-feeds are already closed by the
        engine before this is called; do not close/remove feeds here. Only clean up
        strategy-specific resources here.
        """
        # All infrastructure cleanup now handled externally
        logger.debug(f"{self.__class__.__name__} default `on_stop` called in state {self.state.name}")

    def on_error(self, exc: Exception) -> None:
        """Called when the strategy transitions to ERROR after an unhandled exception.

        This hook is intended for user-level logging, alerting, or releasing custom resources.
        Infrastructure cleanup (feeds, subscriptions, brokers/providers) should be handled by the
        engine. Keep this method fast and robust; avoid raising exceptions here.

        Args:
            exc (Exception): The exception that caused the strategy to enter ERROR.
        """
        logger.error(f"{self.__class__.__name__} `on_error` in state {self.state.name}: {exc}")

    # endregion

    # region Events & EventFeeds

    @abstractmethod  # Made abstract to prevent silent failures - ensures all strategies implement event handling
    def on_event(self, event: Event):
        """Universal callback receiving complete event wrapper.

        This method receives the full event context including:
        - dt_received (when event entered our system)
        - dt_event (official event timestamp)
        - Complete event metadata

        This is the single central event handling method that must be implemented
        by all strategy subclasses to handle all types of events.

        Args:
            event (Event): The complete event wrapper (BarEvent, TradeTickEvent, etc.)
        """
        pass

    def add_event_feed(
        self,
        feed_name: str,
        event_feed: EventFeed,
        callback: Callable | None = None,
        *,
        use_for_simulated_fills: bool | Callable[[Event], bool] = False,
    ) -> None:
        """Attach an EventFeed to this Strategy.

        Connect an EventFeed so this Strategy can receive events from it. Call this during
        `on_start` (when the Strategy is ADDED) or later while RUNNING.

        Under the shared engine timeline model, all strategies in a `TradingEngine` share
        one simulated "now". When you add a new EventFeed while the engine is already
        RUNNING and has processed some events, the engine ensures global chronological
        ordering by calling `EventFeed.remove_events_before` with the current engine time.
        This means the new feed will never emit events that are "in the past" relative to
        the rest of the system.

        Args:
            feed_name (str): User-assigned name for this feed, unique within this Strategy.
                This value appears in logs and is required later to remove the feed with
                `remove_event_feed`. Choose a stable, descriptive name, for example:
                "binance_btcusdt_1m".
            event_feed (EventFeed): The EventFeed instance to attach.
            callback (Optional[Callable]): Optional event handler. If None, uses `self.on_event`.
                If you explicitly do not need to notify your Strategy, you can use
                `callback = lambda e: None`.
            use_for_simulated_fills: Controls if and how this EventFeed is used to drive
                simulated fills in simulated brokers. Use False
                (default) to never drive simulated fills, True to use all events, or
                provide a Callable[[Event], bool] that returns True only for Event(s)
                that should drive simulated fills.

        Raises:
            RuntimeError: If $_trading_engine is None or $state does not allow adding feeds.
            ValueError: If $feed_name is already used for this Strategy.
        """
        engine = self._require_trading_engine()

        # Check: Strategy must be in $state, where adding feeds make sense (only in states ADDED or RUNNING)
        if not (self._state_machine.can_execute_action(StrategyAction.START_STRATEGY) or self.state == StrategyState.RUNNING):
            valid_actions = [a.value for a in self._state_machine.list_valid_actions()]
            raise RuntimeError(f"Cannot call `add_event_feed` because $state ({self.state.name}) does not allow adding feeds. Valid actions: {valid_actions}. Call it from `on_start` or when the strategy is RUNNING.")

        # If callback function was not provided, let's use the default `on_event` callback
        if callback is None:
            callback = self.on_event

        # Delegate to TradingEngine
        engine.add_event_feed_for_strategy(
            strategy=self,
            feed_name=feed_name,
            event_feed=event_feed,
            callback=callback,
            use_for_simulated_fills=use_for_simulated_fills,
        )

    def remove_event_feed(self, feed_name: str) -> None:
        """Detach an EventFeed by its user-assigned name.

        Safe to call even if the feed has already finished naturally (for example, historical
        data feeds that completed).

        Args:
            feed_name (str): The user-assigned name previously passed to `add_event_feed`.

        Raises:
            RuntimeError: If $_trading_engine is None or $state is not RUNNING.
        """
        engine = self._require_trading_engine()

        # Check: state must be RUNNING to remove feeds
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.list_valid_actions()]
            raise RuntimeError(f"Cannot call `remove_event_feed` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}")

        # Delegate to TradingEngine
        engine.remove_event_feed_from_strategy(self, feed_name)

    # endregion

    # region Brokers

    @property
    def brokers(self) -> dict[str, Broker]:
        """Get all Broker instances added to the attached TradingEngine.

        The returned mapping is backed by the engine's broker registry:

        - Keys are broker *names* as passed to `TradingEngine.add_broker`.
        - Values are Broker instances, each representing one logical account.

        Use this primarily for inspection and advanced wiring (for example,
        picking a Broker dynamically). For most strategies it is clearer to
        receive concrete Broker instances via configuration (for example,
        constructor arguments like `$sim_broker` and `$live_broker`).

        Returns:
            dict[str, Broker]: Mapping from broker name to Broker instance.

        Raises:
            RuntimeError: If $_trading_engine is None.
        """
        return self._require_trading_engine().brokers

    def get_broker(self, name: str) -> Broker:
        """Get a Broker by its registered name from the attached TradingEngine.

        This is a thin convenience wrapper over the engine-level broker
        registry. It simply returns the Broker instance that was added to the
        TradingEngine under $name.

        For most strategies it is clearer to inject a specific Broker instance
        via constructor parameters and store it on the Strategy. Use this
        helper only for simple wiring or debugging when you already know the
        broker name.

        Args:
            name: Broker name as registered via `TradingEngine.add_broker`.

        Returns:
            The Broker instance registered under $name.

        Raises:
            RuntimeError: If $_trading_engine is None.
            KeyError: If no Broker with $name is registered in the attached TradingEngine.
        """
        engine = self._require_trading_engine()

        # Check: broker name must be present in the attached TradingEngine
        if name not in engine.brokers:
            raise KeyError(f"Cannot call `get_broker` because Broker named '{name}' is not registered in the attached TradingEngine. Add the broker using `add_broker` first.")

        result = engine.brokers[name]
        return result

    # endregion

    # region Orders

    def submit_order(self, order: Order, broker: Broker) -> None:
        """Submit an order for execution.

        Allowed only when the strategy is RUNNING.

        Args:
            order (Order): The order to submit for execution.
            broker (Broker): The broker to submit the order to.

        Raises:
            RuntimeError: If $trading_engine is None or $state is not RUNNING.
        """
        engine = self._require_trading_engine()

        # Check: state must be RUNNING to submit orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.list_valid_actions()]
            raise RuntimeError(f"Cannot call `submit_order` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}")

        engine.submit_order(order, broker, self)

    def cancel_order(self, order: Order) -> None:
        """Cancel an existing order.

        Allowed only when the strategy is RUNNING.

        Args:
            order (Order): The order to cancel.

        Raises:
            RuntimeError: If $trading_engine is None or $state is not RUNNING.
            KeyError: If $order was not submitted through this Strategy.
        """
        engine = self._require_trading_engine()

        # Check: state must be RUNNING to cancel orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.list_valid_actions()]
            raise RuntimeError(f"Cannot call `cancel_order` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}")

        engine.cancel_order(order)

    def modify_order(self, order: Order) -> None:
        """Modify an existing order.

        Allowed only when the strategy is RUNNING.

        Args:
            order (Order): The order to modify with updated parameters.

        Raises:
            RuntimeError: If $trading_engine is None or $state is not RUNNING.
            KeyError: If $order was not submitted through this Strategy.
        """
        engine = self._require_trading_engine()

        # Check: state must be RUNNING to modify orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.list_valid_actions()]
            raise RuntimeError(f"Cannot call `modify_order` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}")

        engine.modify_order(order)

    # endregion

    # region Broker callbacks

    def on_execution(self, execution: Execution) -> None:
        """Called when an execution (fill/partial-fill) happens for $execution.order.

        Args:
            execution: The execution that occurred.
        """
        logger.debug(f"Strategy named '{self.name}' (class {self.__class__.__name__}) received execution for Order $id ('{execution.order.id}')")

    def on_order_updated(self, order: Order) -> None:
        """Called when $order changes one of its attributes (most common is filled/unfilled or order-state).

        Args:
            order: The order that was updated.
        """
        logger.debug(f"Strategy named '{self.name}' (class {self.__class__.__name__}) received order update for Order $id ('{order.id}')")

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, state={self.state.name})"

    # endregion
