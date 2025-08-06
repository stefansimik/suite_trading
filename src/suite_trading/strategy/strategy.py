from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Callable, Optional
from suite_trading.domain.event import Event
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.broker import Broker
from suite_trading.strategy.strategy_state_machine import StrategyState, StrategyAction, create_strategy_state_machine

if TYPE_CHECKING:
    from suite_trading.platform.engine.trading_engine import TradingEngine


class Strategy(ABC):
    # region Lifecycle

    def __init__(self):
        """Initialize a new strategy.

        Sets initial lifecycle state to NEW. Engine reference is None until added by
        TradingEngine.
        """
        self._trading_engine = None
        self._state_machine = create_strategy_state_machine()

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

    # region Event delivery

    def request_event_delivery(
        self,
        name: str,
        event_type: type,
        parameters: dict,
        provider_ref: str,
        callback: Optional[Callable] = None,
    ) -> None:
        """Request event delivery for the specified parameters.

        Sets up an event delivery mechanism that will call your callback function when events
        become available. Events may arrive immediately (historical), over time (live), or may be
        finite (historical series) or effectively unbounded (live feeds).

        Args:
            name: Unique name for this delivery request within the strategy.
            event_type: Type of events to receive (e.g., NewBarEvent).
            parameters: Dictionary with event-specific parameters.
            provider_ref: Reference name of the provider to use for this request.
            callback: Function to call when events are received. If omitted, defaults to
                self.on_event. Keyword-only.

        Raises:
            ValueError: If $name is already in use for this strategy.
            RuntimeError: If $trading_engine is None or $state is not ADDED/RUNNING.
            UnsupportedEventTypeError: If provider doesn't support the $event_type.
            UnsupportedConfigurationError: If provider doesn't support the configuration.
        """
        # Check: trading engine must be attached before requesting event delivery
        if self._trading_engine is None:
            raise RuntimeError(
                "Cannot call `request_event_delivery` because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Check: state must allow event delivery (ADDED or RUNNING)
        if not (self._state_machine.can_execute_action(StrategyAction.START_STRATEGY) or self.state == StrategyState.RUNNING):
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(
                "Cannot call `request_event_delivery` because $state "
                f"({self.state.name}) does not allow request data. "
                f"Valid actions: {valid_actions}. Call it from `on_start` or when the strategy is RUNNING.",
            )

        # Default to universal handler if not provided
        if callback is None:
            callback = self.on_event

        # Delegate to TradingEngine
        self._trading_engine.request_event_delivery_for_strategy(
            strategy=self,
            name=name,
            event_type=event_type,
            parameters=parameters,
            provider_ref=provider_ref,
            callback=callback,
        )

    def cancel_event_delivery(self, name: str) -> None:
        """Cancel an event delivery request by name.

        Safe to call even if the delivery has already completed naturally (e.g., historical data).

        Args:
            name: Name of the delivery request to cancel.

        Raises:
            ValueError: If $name is not found for this strategy.
            RuntimeError: If $trading_engine is None or $state is not RUNNING.
        """
        # Check: trading engine must be attached before canceling event delivery
        if self._trading_engine is None:
            raise RuntimeError(
                "Cannot call `cancel_event_delivery` because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Check: state must be RUNNING to cancel event delivery
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(
                f"Cannot call `cancel_event_delivery` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}",
            )

        # Delegate to TradingEngine - no local tracking
        self._trading_engine.cancel_event_delivery_for_strategy(self, name)

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
                "Cannot call `submit_order` because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                "Cannot call `cancel_order` because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                "Cannot call `modify_order` because $trading_engine is None. Add the strategy to a TradingEngine first.",
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
                "Cannot call `get_active_orders` because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )
        # Check: state must be RUNNING to retrieve active orders
        if self.state != StrategyState.RUNNING:
            valid_actions = [a.value for a in self._state_machine.get_valid_actions()]
            raise RuntimeError(
                f"Cannot call `get_active_orders` because $state ({self.state.name}) is not RUNNING. Valid actions: {valid_actions}",
            )

        return self._trading_engine.get_active_orders(broker)

    # endregion

    # region Internal

    def _set_trading_engine(self, trading_engine: "TradingEngine"):
        """Attach the trading engine reference.

        This method is called by TradingEngine when the strategy is added. It does not change
        lifecycle $state. TradingEngine is responsible for transitioning to ADDED after successful
        registration.

        Args:
            trading_engine (TradingEngine): The trading engine instance.
        """
        self._trading_engine = trading_engine

    # endregion
