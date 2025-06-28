from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.tick.trade_tick import TradeTick
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick
from suite_trading.domain.instrument import Instrument
from suite_trading.platform.messaging.topic_protocol import TopicProtocol
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.platform.engine.trading_engine import TradingEngine
    from suite_trading.platform.cache import Cache


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

    @property
    def cache(self) -> "Cache":
        """Access to the data cache.

        Returns:
            Cache: The cache instance from the trading engine.

        Raises:
            RuntimeError: If the strategy is not added to a TradingEngine.
        """
        if self._trading_engine is None:
            raise RuntimeError(f"Strategy '{self.name}' must be added to TradingEngine before accessing cache")
        return self._trading_engine.cache

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
            self.unsubscribe_bars(bar_type)

    # -----------------------------------------------
    # SUBSCRIBE TO DATA
    # -----------------------------------------------

    def subscribe_bars(self, bar_type: BarType):
        """Subscribe to bar data for a specific bar type.

        Args:
            bar_type (BarType): The type of bar to subscribe to.
        """
        if self._trading_engine is None:
            raise RuntimeError(f"$strategy '{self.name}' must be added to a TradingEngine before subscribing to bars")

        # Subscribe to the topic
        topic = TopicProtocol.create_bar_topic(bar_type)
        self._trading_engine.message_bus.subscribe(topic, self.on_bar)

        # Remember the subscribed bar type
        self._subscribed_bar_types.add(bar_type)

    def unsubscribe_bars(self, bar_type: BarType):
        """Unsubscribe from bar data for a specific bar type.

        Args:
            bar_type (BarType): The type of bar to unsubscribe from.
        """
        if self._trading_engine is None:
            return

        if bar_type in self._subscribed_bar_types:
            # Create a standardized topic name for the bar type
            topic = TopicProtocol.create_bar_topic(bar_type)

            # Unsubscribe from the topic
            self._trading_engine.message_bus.unsubscribe(topic, self.on_bar)
            self._subscribed_bar_types.remove(bar_type)

    def subscribe_trade_ticks(self, instrument: Instrument):
        """Subscribe to trade tick data for a specific instrument.

        Args:
            instrument (Instrument): The instrument to subscribe to.
        """
        # TODO: implement
        pass

    def subscribe_quote_ticks(self, instrument: Instrument):
        """Subscribe to quote tick data for a specific instrument.

        Args:
            instrument (Instrument): The instrument to subscribe to.
        """
        # TODO: implement
        pass

    # -----------------------------------------------
    # DATA HANDLERS
    # -----------------------------------------------

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
