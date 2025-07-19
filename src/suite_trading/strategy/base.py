from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.tick.trade_tick import TradeTick
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick
from suite_trading.domain.instrument import Instrument
from suite_trading.platform.messaging.topic_protocol import TopicProtocol
from suite_trading.platform.messaging.message_bus import MessageBus
from typing import TYPE_CHECKING

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
        self._subscribed_trade_tick_instruments = set()  # Track subscribed trade tick instruments
        self._subscribed_quote_tick_instruments = set()  # Track subscribed quote tick instruments

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

        Automatically unsubscribes from all bar, trade tick, and quote tick subscriptions.
        """
        # Unsubscribe from all bar topics
        for bar_type in list(self._subscribed_bar_types):
            self.unsubscribe_bars(bar_type)

        # Unsubscribe from all trade tick topics
        for instrument in list(self._subscribed_trade_tick_instruments):
            self.unsubscribe_trade_ticks(instrument)

        # Unsubscribe from all quote tick topics
        for instrument in list(self._subscribed_quote_tick_instruments):
            self.unsubscribe_quote_ticks(instrument)

    # -----------------------------------------------
    # SUBSCRIBE TO DATA
    # -----------------------------------------------

    def subscribe_bars(self, bar_type: BarType):
        """Subscribe to bar data for a specific bar type with automatic demand-based publishing.

        Args:
            bar_type (BarType): The type of bar to subscribe to.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `subscribe_bars` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Request market data (will start publishing if first subscriber)
        self._trading_engine.subscribe_to_bars(bar_type, self)

        # Subscribe to the message bus topic
        topic = TopicProtocol.create_bar_topic(bar_type)
        MessageBus.get().subscribe(topic, self.on_event)

        # Remember the subscribed bar type
        self._subscribed_bar_types.add(bar_type)

    def unsubscribe_bars(self, bar_type: BarType):
        """Unsubscribe from bar data for a specific bar type with automatic cleanup.

        Args:
            bar_type (BarType): The type of bar to unsubscribe from.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `unsubscribe_bars` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        if bar_type in self._subscribed_bar_types:
            # Unsubscribe from the message bus topic
            topic = TopicProtocol.create_bar_topic(bar_type)
            MessageBus.get().unsubscribe(topic, self.on_event)
            self._subscribed_bar_types.remove(bar_type)

            # Stop market data (will stop publishing if last subscriber)
            self._trading_engine.unsubscribe_from_bars(bar_type, self)

    def subscribe_trade_ticks(self, instrument: Instrument):
        """Subscribe to trade tick data for a specific instrument with automatic demand-based publishing.

        Args:
            instrument (Instrument): The instrument to subscribe to.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `subscribe_trade_ticks` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Request market data (will start publishing if first subscriber)
        self._trading_engine.subscribe_to_trade_ticks(instrument, self)

        # Subscribe to the message bus topic
        topic = TopicProtocol.create_trade_tick_topic(instrument)
        MessageBus.get().subscribe(topic, self.on_event)

        # Remember the subscribed instrument
        self._subscribed_trade_tick_instruments.add(instrument)

    def subscribe_quote_ticks(self, instrument: Instrument):
        """Subscribe to quote tick data for a specific instrument with automatic demand-based publishing.

        Args:
            instrument (Instrument): The instrument to subscribe to.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `subscribe_quote_ticks` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        # Request market data (will start publishing if first subscriber)
        self._trading_engine.subscribe_to_quote_ticks(instrument, self)

        # Subscribe to the message bus topic
        topic = TopicProtocol.create_quote_tick_topic(instrument)
        MessageBus.get().subscribe(topic, self.on_event)

        # Remember the subscribed instrument
        self._subscribed_quote_tick_instruments.add(instrument)

    def unsubscribe_trade_ticks(self, instrument: Instrument):
        """Unsubscribe from trade tick data for a specific instrument with automatic cleanup.

        Args:
            instrument (Instrument): The instrument to unsubscribe from.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `unsubscribe_trade_ticks` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        if instrument in self._subscribed_trade_tick_instruments:
            # Unsubscribe from the message bus topic
            topic = TopicProtocol.create_trade_tick_topic(instrument)
            MessageBus.get().unsubscribe(topic, self.on_event)
            self._subscribed_trade_tick_instruments.remove(instrument)

            # Stop market data (will stop publishing if last subscriber)
            self._trading_engine.unsubscribe_from_trade_ticks(instrument, self)

    def unsubscribe_quote_ticks(self, instrument: Instrument):
        """Unsubscribe from quote tick data for a specific instrument with automatic cleanup.

        Args:
            instrument (Instrument): The instrument to unsubscribe from.
        """
        if self._trading_engine is None:
            raise RuntimeError(
                f"Cannot call `unsubscribe_quote_ticks` on strategy '{self.name}' because $trading_engine is None. Add the strategy to a TradingEngine first.",
            )

        if instrument in self._subscribed_quote_tick_instruments:
            # Unsubscribe from the message bus topic
            topic = TopicProtocol.create_quote_tick_topic(instrument)
            MessageBus.get().unsubscribe(topic, self.on_event)
            self._subscribed_quote_tick_instruments.remove(instrument)

            # Stop market data (will stop publishing if last subscriber)
            self._trading_engine.unsubscribe_from_quote_ticks(instrument, self)

    # -----------------------------------------------
    # DATA HANDLERS
    # -----------------------------------------------

    def on_event(self, event: Event):
        """Universal callback receiving complete event wrapper.

        This method receives the full event context including:
        - dt_received (when event entered our system)
        - dt_event (official event timestamp)
        - event_type (for routing/filtering)
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
        # TODO: Let's think, what is better, if we should check event_type
        #   as string or it would be better to check `instanceof` and compare real type

        if event.event_type == "bar":
            self.on_bar(event.bar)  # Extract bar from NewBarEvent
        elif event.event_type == "trade_tick":
            self.on_trade_tick(event.trade_tick)  # Extract from NewTradeTickEvent
        elif event.event_type == "quote_tick":
            self.on_quote_tick(event.quote_tick)  # Extract from NewQuoteTickEvent
        # Add other event types as needed

    def on_bar(self, bar: Bar):
        """Called when a new bar is received.

        This method should be overridden by subclasses to implement
        strategy logic for processing bar data.

        Args:
            bar (Bar): The bar data received.
        """
        pass

    def on_trade_tick(self, trade_tick: TradeTick):
        """Called when a new trade tick is received.

        This method should be overridden by subclasses to implement
        strategy logic for processing trade tick data.

        Args:
            trade_tick (TradeTick): The trade tick data received.
        """
        pass

    def on_quote_tick(self, quote_tick: QuoteTick):
        """Called when a new quote tick is received.

        This method should be overridden by subclasses to implement
        strategy logic for processing quote tick data.

        Args:
            quote_tick (QuoteTick): The quote tick data received.
        """
        pass
