import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, List, Callable, Optional
from suite_trading.domain.event import Event
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy_state_machine import StrategyState, StrategyAction, create_strategy_state_machine

if TYPE_CHECKING:
    from suite_trading.platform.engine.trading_engine import TradingEngine

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

    def __init__(self):
        """Initialize a new strategy.

        Sets initial lifecycle state to NEW. Engine reference is None until added by
        TradingEngine.
        """
        self._trading_engine = None
        self._state_machine = create_strategy_state_machine()

    # endregion

    # region Attach engine

    def set_trading_engine(self, trading_engine: "TradingEngine") -> None:
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
        # Check: engine must be attached before clearing
        if self._trading_engine is None:
            raise RuntimeError(
                "Cannot call `_clear_trading_engine` because $_trading_engine is None.",
            )

        self._trading_engine = None

    # endregion

    # region State

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
    def last_event_time(self) -> Optional[datetime]:
        """Get time (`dt_event`) of the last event for this strategy.

        Returns the dt_event of the last processed event for this strategy. Advances only when this
        strategy processes an event. Each strategy has its own independent timeline.
        """
        if self._trading_engine is None:
            return None

        return self._trading_engine._strategy_clocks_dict[self].last_event_time

    @property
    def wall_clock_time(self) -> Optional[datetime]:
        """Get the latest known wall clock time (max `dt_received` from all events) for this strategy.

        Returns the maximum dt_received seen across all events processed by this strategy. Use this
        value for live cutoffs, timeouts, and latency checks. This is separate from
        last_event_time.
        """
        # TODO:  Strategy state machine will be extended in the future with more granular state like: HISTORICAL / TRANSITION / LIVE
        # This property will have to be updated then and computed based on the current state:
        # - HISTORICAL: keep using the maximum dt_received from processed events
        # - TRANSITION: decide behavior when this state is introduced
        # - LIVE: use the real system clock (current NOW) for a realistic wall-clock time

        if self._trading_engine is None:
            return None

        return self._trading_engine._strategy_clocks_dict[self].wall_clock_time

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
            event (Event): The complete event wrapper (NewBarEvent, NewTradeTickEvent, etc.)
        """
        pass

    def add_event_feed(
        self,
        feed_name: str,
        event_feed: EventFeed,
        callback: Optional[Callable] = None,
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
        # Check: TradingEngine must be attached in this Strategy
        if self._trading_engine is None:
            raise RuntimeError("Cannot call `add_event_feed` because $_trading_engine is None. Add the strategy to a TradingEngine first.")

        # Check: Strategy must be in $state, where adding feeds make sense (only in states ADDED or RUNNING)
        if not (self._state_machine.can_execute_action(StrategyAction.START_STRATEGY) or self.state == StrategyState.RUNNING):
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(f"Cannot call `add_event_feed` because $state ({self.state.name}) does not allow adding feeds. Valid actions: {valid_actions}. Call it from `on_start` or when the strategy is RUNNING.")

        # If callback function was not provided, let's use the default `on_event` callback
        if callback is None:
            callback = self.on_event

        # Delegate to TradingEngine
        self._trading_engine.add_event_feed_for_strategy(
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
        # Check: engine must be attached
        if self._trading_engine is None:
            raise RuntimeError("Cannot call `remove_event_feed` because $_trading_engine is None. Add the strategy to a TradingEngine first.")

        # Check: state must be RUNNING to remove feeds
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(f"Cannot call `remove_event_feed` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}")

        # Delegate to TradingEngine
        self._trading_engine.remove_event_feed_from_strategy(self, feed_name)

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
        # Check: trading engine must be attached before submitting orders
        if self._trading_engine is None:
            raise RuntimeError("Cannot call `submit_order` because $_trading_engine is None. Add the strategy to a TradingEngine first.")

        # Check: state must be RUNNING to submit orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(f"Cannot call `submit_order` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}")

        self._trading_engine.submit_order(order, broker)

    # FIXME: Order is already created and should already know to which Broker it is attached.
    #   So we should not need to pass it as an argument here.
    def cancel_order(self, order: Order, broker: Broker) -> None:
        """Cancel an existing order.

        Allowed only when the strategy is RUNNING.

        Args:
            order (Order): The order to cancel.
            broker (Broker): The broker to cancel the order with.

        Raises:
            RuntimeError: If $trading_engine is None or $state is not RUNNING.
        """
        # Check: trading engine must be attached before canceling orders
        if self._trading_engine is None:
            raise RuntimeError(
                "Cannot call `cancel_order` because $_trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Check: state must be RUNNING to cancel orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(
                f"Cannot call `cancel_order` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}",
            )

        self._trading_engine.cancel_order(order, broker)

    # FIXME: Order is already created and should already know to which Broker it is attached.
    #   So we should not need to pass it as an argument here.
    def modify_order(self, order: Order, broker: Broker) -> None:
        """Modify an existing order.

        Allowed only when the strategy is RUNNING.

        Args:
            order (Order): The order to modify with updated parameters.
            broker (Broker): The broker to modify the order with.

        Raises:
            RuntimeError: If $trading_engine is None or $state is not RUNNING.
        """
        # Check: trading engine must be attached before modifying orders
        if self._trading_engine is None:
            raise RuntimeError("Cannot call `modify_order` because $_trading_engine is None. Add the strategy to a TradingEngine first.")

        # Check: state must be RUNNING to modify orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(f"Cannot call `modify_order` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}")

        self._trading_engine.modify_order(order, broker)

    # TODO: Allow filtering only orders created by this Strategy
    def get_active_orders(self, broker: Broker) -> List[Order]:
        """Get all currently active orders.

        Allowed only when the strategy is RUNNING.

        Args:
            broker (Broker): The broker to get active orders from.

        Returns:
            List[Order]: List of all active orders for the specified broker.

        Raises:
            RuntimeError: If $trading_engine is None or $state is not RUNNING.
        """
        # Check: trading engine must be attached before retrieving active orders
        if self._trading_engine is None:
            raise RuntimeError("Cannot call `get_active_orders` because $_trading_engine is None. Add the strategy to a TradingEngine first.")

        # Check: state must be RUNNING to retrieve active orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(f"Cannot call `get_active_orders` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}")

        return self._trading_engine.get_active_orders(broker)

    # endregion
