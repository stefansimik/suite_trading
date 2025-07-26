from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Sequence
from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.broker import Broker

if TYPE_CHECKING:
    from suite_trading.platform.engine.trading_engine import TradingEngine


class Strategy:
    def __init__(self, name: str):
        """Initialize a new strategy.

        Args:
            name (str): The unique name of the strategy.

        Raises:
            ValueError: If the strategy name has empty characters at the start or end.
        """
        # Validate that the strategy name doesn't have empty characters at the start and end
        if name != name.strip():
            raise ValueError(f"$name cannot have empty characters at the start or end, but provided value is: '{name}'")

        self.name = name
        self._trading_engine = None

        self._subscribed_bar_types = set()  # Track subscribed bar types

    def _set_trading_engine(self, trading_engine: "TradingEngine"):
        """Set the trading engine reference.

        This method is called by the TradingEngine when the strategy is added to it.
        It is not expected to be called directly by subclasses.

        Args:
            trading_engine (TradingEngine): The trading engine instance.
        """
        self._trading_engine = trading_engine

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

        Automatically unsubscribes from all bar subscriptions.
        """
        # Unsubscribe from all bar topics
        for bar_type in list(self._subscribed_bar_types):
            self.unsubscribe_from_live_bars(bar_type)

    # -----------------------------------------------
    # SUBSCRIBE TO DATA
    # -----------------------------------------------

    # -----------------------------------------------
    # MARKET DATA REQUESTS
    # -----------------------------------------------

    # TODO: Check
    def get_historical_bars_series(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: Optional[datetime] = None,
    ) -> Sequence[Bar]:
        """Get historical bars as a complete series.

        Args:
            bar_type (BarType): The type of bar to request.
            from_dt (datetime): Start date and time for historical data.
            until_dt (Optional[datetime]): End date and time for historical data.
                If None, requests data until the most recent available.

        Returns:
            Sequence[Bar]: Complete series of historical bars.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `get_historical_bars_series` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        return self._trading_engine.get_historical_bars_series(bar_type, from_dt, until_dt)

    # TODO: Check
    def stream_historical_bars(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: Optional[datetime] = None,
    ) -> None:
        """Stream historical bars through the callback system.

        Historical bars will be delivered through the on_bar callback method
        with is_historical=True context.

        Args:
            bar_type (BarType): The type of bar to stream.
            from_dt (datetime): Start date and time for historical data.
            until_dt (Optional[datetime]): End date and time for historical data.
                If None, streams data until the most recent available.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `stream_historical_bars` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.stream_historical_bars(bar_type, from_dt, until_dt)

    # TODO: Check
    def subscribe_to_live_bars(self, bar_type: BarType) -> None:
        """Subscribe to live bar data for a specific bar type.

        Live bars will be delivered through the on_bar callback method
        with is_historical=False context.

        Args:
            bar_type (BarType): The type of bar to subscribe to.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `subscribe_to_live_bars` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.subscribe_to_live_bars(bar_type, self)

        # Remember the subscribed bar type for cleanup during stop
        self._subscribed_bar_types.add(bar_type)

    # TODO: Check
    def subscribe_to_live_bars_with_history(
        self,
        bar_type: BarType,
        history_days: int,
    ) -> None:
        """Subscribe to live bars with historical backfill.

        First delivers historical bars for the specified number of days,
        then continues with live bars. Historical bars are delivered with
        is_historical=True, live bars with is_historical=False.

        Args:
            bar_type (BarType): The type of bar to subscribe to.
            history_days (int): Number of days of historical data to backfill.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `subscribe_to_live_bars_with_history` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.subscribe_to_live_bars_with_history(bar_type, history_days, self)

    def unsubscribe_from_live_bars(self, bar_type: BarType) -> None:
        """Unsubscribe from live bar data for a specific bar type.

        Args:
            bar_type (BarType): The type of bar to unsubscribe from.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `unsubscribe_from_live_bars` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        if bar_type in self._subscribed_bar_types:
            # Ask TradingEngine to handle all unsubscription details
            self._trading_engine.unsubscribe_from_live_bars(bar_type, self)

            # Remove from our local tracking
            self._subscribed_bar_types.remove(bar_type)

    # -----------------------------------------------
    # DATA HANDLERS
    # -----------------------------------------------

    def on_event(self, event: Event):
        """Universal callback receiving complete event wrapper.

        This method receives the full event context including:
        - dt_received (when event entered our system)
        - dt_event (official event timestamp)
        - Complete event metadata

        Override this method when you need access to event metadata.
        The default implementation routes events to specific callbacks.

        Args:
            event (Event): The complete event wrapper (NewBarEvent, NewTradeTickEvent, etc.)
        """
        # Default implementation routes to specific handlers
        self._distribute_event_to_specific_callbacks(event)

    def _distribute_event_to_specific_callbacks(self, event: Event):
        """Internal routing method to distribute events to specific callbacks.

        This method extracts the pure data objects from event wrappers and
        calls the appropriate specific callback methods (on_bar, on_trade_tick, etc.).

        Args:
            event (Event): The event wrapper to route to specific callbacks.
        """
        if isinstance(event, NewBarEvent):
            self.on_bar(event.bar, event.is_historical)  # Extract bar and historical context from NewBarEvent
        # Add other event types as needed

    def on_bar(self, bar: Bar, is_historical: bool):
        """Called when a new bar is received.

        This method should be overridden by subclasses to implement
        strategy logic for processing bar data.

        Args:
            bar (Bar): The bar data received.
            is_historical (bool): Whether this bar data is historical or live.
        """
        pass

    def on_historical_bars_series(self, bars: Sequence[Bar]):
        """Called when a series of historical bars is received.

        This method is called when requesting historical bar data series,
        typically from methods like get_historical_bars_series(). All bars
        in the series are historical data.

        This method should be overridden by subclasses to implement
        strategy logic for processing historical bar series data.

        Args:
            bars (Sequence[Bar]): The sequence of historical bar data received.
        """
        pass

    # -----------------------------------------------
    # ORDER MANAGEMENT
    # -----------------------------------------------

    def submit_order(self, order: Order, broker: Broker) -> None:
        """Submit an order for execution.

        Args:
            order (Order): The order to submit for execution.
            broker (Broker): The broker to submit the order to.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `submit_order` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.submit_order(order, broker)

    def cancel_order(self, order: Order, broker: Broker) -> None:
        """Cancel an existing order.

        Args:
            order (Order): The order to cancel.
            broker (Broker): The broker to cancel the order with.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `cancel_order` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.cancel_order(order, broker)

    def modify_order(self, order: Order, broker: Broker) -> None:
        """Modify an existing order.

        Args:
            order (Order): The order to modify with updated parameters.
            broker (Broker): The broker to modify the order with.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `modify_order` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        self._trading_engine.modify_order(order, broker)

    def get_active_orders(self, broker: Broker) -> List[Order]:
        """Get all currently active orders.

        Args:
            broker (Broker): The broker to get active orders from.

        Returns:
            List[Order]: List of all active orders for the specified broker.

        Raises:
            RuntimeError: If trading engine is not set.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `get_active_orders` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        return self._trading_engine.get_active_orders(broker)
