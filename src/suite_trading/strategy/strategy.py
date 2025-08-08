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

    # region Init strategy

    def __init__(self):
        """Initialize a new strategy.

        Sets initial lifecycle state to NEW. Engine reference is None until added by
        TradingEngine.
        """
        self._trading_engine = None
        self._state_machine = create_strategy_state_machine()

    # endregion

    # region Attach engine

    def _set_trading_engine(self, trading_engine: "TradingEngine") -> None:
        """Attach the trading engine reference.

        This method is called by TradingEngine when the strategy is added. It does not change
        lifecycle $state. TradingEngine is responsible for transitioning to ADDED after successful
        registration.

        Args:
            trading_engine (TradingEngine): The trading engine instance.

        Raises:
            RuntimeError: If $_trading_engine is already set or $state is not NEW.
        """
        # Check: engine must not be already attached
        if self._trading_engine is not None:
            raise RuntimeError(
                "Cannot call `_set_trading_engine` because $_trading_engine is already set.",
            )
        # Check: state must be NEW when attaching to an engine
        if self.state != StrategyState.NEW:
            raise RuntimeError(
                (f"Cannot call `_set_trading_engine` because $state ({self.state.name}) is not NEW. Provide a fresh instance."),
            )
        self._trading_engine = trading_engine

    def _clear_trading_engine(self) -> None:
        """Detach the trading engine reference.

        Called by TradingEngine when the strategy is removed. Does not change lifecycle $state.

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

    # region Query state

    @property
    def state(self) -> StrategyState:
        """Get current lifecycle state.

        Returns:
            StrategyState: Current lifecycle state of this strategy.
        """
        return self._state_machine.current_state

    def is_in_terminal_state(self) -> bool:
        """Check if the strategy is in a terminal state.

        Returns:
            bool: True if the strategy is in a terminal state (STOPPED or ERROR).
        """
        return self._state_machine.is_in_terminal_state()

    # endregion

    # region Query time

    @property
    def last_event_time(self) -> Optional[datetime]:
        """Get the timeline time for this strategy.

        Returns the dt_event of the last processed event for this strategy. Advances only when this
        strategy processes an event. Each strategy has its own independent timeline.
        """
        if self._trading_engine is None:
            return None

        return self._trading_engine._strategy_last_event_time[self]

    @property
    def wall_clock_time(self) -> Optional[datetime]:
        """Get the latest known wall clock time for this strategy.

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

        return self._trading_engine._strategy_wall_clock_time[self]

    # endregion

    # region Lifecycle hooks

    def on_start(self):
        """Called when the strategy is started.

        This method should be overridden by subclasses to implement
        initialization logic when the strategy starts.
        """
        pass

    def on_stop(self):
        """Called when the strategy is stopped.

        This method should be overridden by subclasses to implement
        cleanup logic when the strategy stops.

        Note: All infrastructure cleanup (event feeds, subscriptions) is handled
        automatically by TradingEngine. Only clean up strategy-specific resources here.
        """
        # All infrastructure cleanup now handled externally
        # Override this method to add strategy-specific cleanup only
        pass

    def on_error(self, exc: Exception) -> None:
        """Called when the strategy transitions to ERROR after an unhandled exception.

        This hook is intended for user-level logging, alerting, or releasing custom resources.
        Infrastructure cleanup (feeds, subscriptions, brokers/providers) should be handled by the
        engine. Keep this method fast and robust; avoid raising exceptions here.

        Args:
            exc (Exception): The exception that caused the strategy to enter ERROR.
        """
        pass

    # endregion

    # region Event feeds

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
        name: str,
        event_feed: EventFeed,
        callback: Optional[Callable] = None,
    ) -> None:
        """Attach an EventFeed to this Strategy.

        Connect an EventFeed so this strategy can start receiving events from it. You can call
        this during `on_start` (when the strategy is ADDED) or later while RUNNING.

        Args:
            name: Unique name for this feed within the strategy.
            event_feed: The EventFeed instance to attach.
            callback: Optional; if None, defaults to self.on_event.

        Raises:
            RuntimeError: If $_trading_engine is None or $state does not allow adding feeds.
            ValueError: If $name is already used for this strategy.
        """
        # Check: engine must be attached
        if self._trading_engine is None:
            raise RuntimeError(
                "Cannot call `add_event_feed` because $_trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Check: state must allow adding feeds (ADDED or RUNNING)
        if not (self._state_machine.can_execute_action(StrategyAction.START_STRATEGY) or self.state == StrategyState.RUNNING):
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(
                "Cannot call `add_event_feed` because $state "
                f"({self.state.name}) does not allow adding feeds. "
                f"Valid actions: {valid_actions}. Call it from `on_start` "
                "or when the strategy is RUNNING.",
            )

        # If we didnt specify a callback, use the default `on_event` callback
        if callback is None:
            callback = self.on_event

        self._trading_engine.add_event_feed_for_strategy(
            strategy=self,
            name=name,
            event_feed=event_feed,
            callback=callback,
        )

    def remove_event_feed(self, name: str) -> None:
        """Detach an EventFeed by name.

        Safe to call even if the feed has already finished naturally (e.g., historical data).

        Args:
            name: Name of the feed to remove.

        Raises:
            RuntimeError: If $_trading_engine is None or $state is not RUNNING.
        """
        # Check: engine must be attached
        if self._trading_engine is None:
            raise RuntimeError(
                "Cannot call `remove_event_feed` because $_trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Check: state must be RUNNING to remove feeds
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(
                f"Cannot call `remove_event_feed` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}",
            )

        # Delegate to TradingEngine - no local tracking
        self._trading_engine.remove_event_feed_from_strategy(self, name)

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
            raise RuntimeError(
                "Cannot call `submit_order` because $_trading_engine is None. Add the strategy to a TradingEngine first.",
            )
        # Check: state must be RUNNING to submit orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(
                f"Cannot call `submit_order` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}",
            )

        self._trading_engine.submit_order(order, broker)

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
            raise RuntimeError(
                "Cannot call `modify_order` because $_trading_engine is None. Add the strategy to a TradingEngine first.",
            )
        # Check: state must be RUNNING to modify orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(
                f"Cannot call `modify_order` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}",
            )

        self._trading_engine.modify_order(order, broker)

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
            raise RuntimeError(
                "Cannot call `get_active_orders` because $_trading_engine is None. Add the strategy to a TradingEngine first.",
            )
        # Check: state must be RUNNING to retrieve active orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(
                f"Cannot call `get_active_orders` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}",
            )

        return self._trading_engine.get_active_orders(broker)

    # endregion
