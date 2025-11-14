from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Callable
from suite_trading.domain.event import Event
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy_state_machine import StrategyState, StrategyAction, create_strategy_state_machine

if TYPE_CHECKING:
    from suite_trading.platform.engine.trading_engine import TradingEngine
    from suite_trading.platform.routing.strategy_broker_pair import StrategyBrokerPair
    from suite_trading.domain.order.execution import Execution

logger = logging.getLogger(__name__)


class Strategy(ABC):
    """Base class for all trading strategies with independent timeline management.

    **Timeline Isolation:**
    Each Strategy operates with its own independent timeline, completely isolated from other
    strategies' timelines. This means:

    - **No Global Time Synchronization**: There is no global time that syncs across all strategies
    - **Independent Event Processing**: Each strategy processes events at its own pace and timeline
    - **Flexible Time Ranges**: Strategies can process different time periods simultaneously
    - **Mixed Execution Modes**: Historical backtests and live strategies can run together

    **Benefits:**
    - Run multiple historical backtests with different time periods simultaneously
    - Combine live trading strategies with historical analysis strategies
    - Each strategy maintains its own `last_event_time` based on the last processed event
    - Strategies never interfere with each other's timeline progression

    **Example Use Cases:**
    - Strategy A: Historical backtest from 2020-2023
    - Strategy B: Live trading starting from current time
    - Strategy C: Historical analysis from 2019-2021
    - All three can run simultaneously, each with their own timeline
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

    # region Times

    @property
    def last_event_time(self) -> datetime | None:
        """Get time (`dt_event`) of the last event for this strategy.

        Returns the dt_event of the last processed event for this strategy. Advances only when this
        strategy processes an event. Each strategy has its own independent timeline.
        """
        if self._trading_engine is None:
            return None

        return self._trading_engine._clocks_by_strategy[self].last_event_time

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
    ) -> None:
        """Attach an EventFeed to this Strategy.

        Connect an EventFeed so this strategy can receive events from it. Call this during
        `on_start` (when the strategy is ADDED) or later while RUNNING.

        Args:
            feed_name (str): User-assigned name for this feed, unique within this strategy.
                This value appears in logs and is required later to remove the feed with
                `remove_event_feed`. Choose a stable, descriptive name, for example:
                "binance_btcusdt_1m".
            event_feed (EventFeed): The EventFeed instance to attach.
            callback (Optional[Callable]): Optional event handler. If None, uses `self.on_event`.
                If you explicitly don't need to callback for informing your strategy, then you can use `callback =lambda e: None`.

        Raises:
            RuntimeError: If $_trading_engine is None or $state does not allow adding feeds.
            ValueError: If $feed_name is already used for this strategy.
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
    def brokers(self) -> dict[type[Broker], Broker]:
        """Get all Broker instances added to the attached TradingEngine.

        Returns:
            dict[type[Broker], Broker]: Mapping from concrete Broker class to instance.

        Raises:
            RuntimeError: If $_trading_engine is None.
        """
        return self._require_trading_engine().brokers

    def get_broker(self, broker_type: type[Broker]) -> Broker:
        """Get a specific Broker by its concrete class.

        Args:
            broker_type (type[Broker]): The concrete Broker class to retrieve.

        Returns:
            Broker: The Broker instance registered for the given class.

        Raises:
            RuntimeError: If $_trading_engine is None.
            KeyError: If the requested broker type is not added to the attached TradingEngine.
        """
        engine = self._require_trading_engine()
        try:
            return engine.brokers[broker_type]
        except KeyError:
            raise KeyError(f"Cannot call `get_broker` because broker type '{broker_type.__name__}' is not added to the attached TradingEngine. Add the broker to the TradingEngine using `add_broker` first.")

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

    def get_routing_for_order(self, order: Order) -> StrategyBrokerPair:
        """Lookup  route (strategy, broker) for $order.

        Args:
            order: The order to look up.

        Raises:
            KeyError: If $order was not submitted via this TradingEngine.
        """
        engine = self._require_trading_engine()
        return engine.get_routing_for_order(order)

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
