import logging
import heapq
from typing import Optional, List
from datetime import datetime
from suite_trading.strategy.base import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.message_priority import SubscriberPriority
from suite_trading.platform.messaging.topic_protocol import TopicProtocol
from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order import Order
from suite_trading.platform.cache import Cache
from suite_trading.platform.providers.historical_market_data_provider import HistoricalMarketDataProvider
from suite_trading.platform.providers.live_market_data_provider import LiveMarketDataProvider
from suite_trading.platform.providers.brokerage_provider import BrokerageProvider
from suite_trading.platform.event_feed.event_feed import EventFeed

logger = logging.getLogger(__name__)


class TradingEngine:
    """Main engine for managing and running trading strategies.

    The TradingEngine works as the main coordinator between strategies and three providers:
    historical market data, live market data, and brokerage operations.

    Strategies don't talk directly to providers - instead, they ask the TradingEngine
    to get market data for them and execute orders through the brokerage provider.

    **Architecture:**
    - **HistoricalMarketDataProvider**: Handles bulk historical data retrieval for strategy initialization
    - **LiveMarketDataProvider**: Manages real-time streaming subscriptions for live trading
    - **BrokerageProvider**: Handles order execution and position management

    **Why this indirect approach is important:**
    - **Safety check**: Engine makes sure the providers are available before subscribing
    - **Stable abstraction layer**: TradingEngine acts as a stable abstraction layer that shields strategies from changes in the underlying providers. The engine provides a consistent interface that doesn't change even when provider implementations or APIs evolve.
    - **Automated connections**: Engine automatically connects and disconnects providers when TradingEngine starts and stops

    This design lets strategies focus on trading decisions while the engine takes care
    of getting the data they need, managing connections, and executing orders.
    """

    def __init__(
        self,
        brokerage_provider: BrokerageProvider,
        historical_data_provider: Optional[HistoricalMarketDataProvider] = None,
        live_data_provider: Optional[LiveMarketDataProvider] = None,
    ):
        """Initialize a new TradingEngine instance.

        Args:
            brokerage_provider (BrokerageProvider): Required provider for trading operations.
            historical_data_provider (Optional[HistoricalMarketDataProvider]): Optional provider for historical market data.
            live_data_provider (Optional[LiveMarketDataProvider]): Optional provider for live market data streaming.

        Uses the singleton Cache and MessageBus instances.
        """
        self.strategies: list[Strategy] = []

        self.historical_data_provider = historical_data_provider
        self.live_data_provider = live_data_provider
        self.brokerage_provider = brokerage_provider

        # EventFeed management
        self._event_feeds: List[EventFeed] = []
        self._event_buffer: List[Event] = []  # Min-heap for chronological ordering
        self._current_time: Optional[datetime] = None
        self._is_running: bool = False

        # Subscribe cache to all bar data with system highest priority
        # This ensures the cache receives and stores data before strategies process it
        MessageBus.get().subscribe("bar::*", Cache.get().on_bar, SubscriberPriority.SYSTEM_HIGHEST)

    def start(self):
        """Start the TradingEngine and all EventFeeds.

        This method connects providers, starts EventFeeds, and begins event processing.
        """
        self._is_running = True

        # Connect providers
        if self.historical_data_provider:
            self.historical_data_provider.connect()
        if self.live_data_provider:
            self.live_data_provider.connect()
        self.brokerage_provider.connect()

        # Connect all EventFeeds
        for feed in self._event_feeds:
            feed.connect()

        # Start strategies
        for strategy in self.strategies:
            strategy.on_start()

        # Start event processing loop
        self._process_events()

    # TODO: Is order here correct? Shouldn't it be in reverse order than in `start` function?
    def stop(self):
        """Stop the TradingEngine and disconnect all EventFeeds.

        This method stops event processing, disconnects EventFeeds, stops strategies,
        and disconnects providers.
        """
        self._is_running = False

        # Disconnect all EventFeeds
        for feed in self._event_feeds:
            feed.disconnect()

        # Stop strategies
        for strategy in self.strategies:
            strategy.on_stop()

        # Disconnect providers
        if self.historical_data_provider:
            self.historical_data_provider.disconnect()
        if self.live_data_provider:
            self.live_data_provider.disconnect()
        self.brokerage_provider.disconnect()

    def add_strategy(self, strategy: Strategy):
        """Add a strategy to the engine.

        Args:
            strategy (Strategy): The strategy to add.

        Raises:
            ValueError: If a strategy with the same name already exists.
        """
        # Make sure each strategy has unique name
        for existing_strategy in self.strategies:
            if existing_strategy.name == strategy.name:
                raise ValueError(
                    f"$strategy cannot be added, because it does not have unique name. Strategy with $name '{strategy.name}' already exists and another one with same name cannot be added again.",
                )

        # Set the trading engine reference in the strategy
        strategy._set_trading_engine(self)
        self.strategies.append(strategy)

    def add_event_feed(self, event_feed: EventFeed):
        """Add an EventFeed to the TradingEngine.

        EventFeeds are the primary way to feed events/data into the TradingEngine.
        All events from EventFeeds are processed chronologically and distributed
        via MessageBus to strategies.

        Args:
            event_feed (EventFeed): The EventFeed to add for event processing.
        """
        self._event_feeds.append(event_feed)

        # TODO: Re-evaluate, why we have to check if this engine is running.
        #   And what happens if it is not running? When the EventFeed will be connected later?
        if self._is_running:
            event_feed.connect()

    def remove_event_feed(self, event_feed: EventFeed):
        """Remove an EventFeed from the TradingEngine.

        Args:
            event_feed (EventFeed): The EventFeed to remove.
        """
        if event_feed in self._event_feeds:
            event_feed.disconnect()
            self._event_feeds.remove(event_feed)

    def get_current_time(self) -> Optional[datetime]:
        """Get the current time from event processing.

        In backtesting mode, this reflects the latest event timestamp.
        In live trading mode, this reflects real-time progression.

        Returns:
            datetime: Current time from event processing, or None if no events processed yet.
        """
        # TODO: TradingEngine will need to have own StateMachine, that will reflect
        #   the state, in which it is right now and based on the state, it will return
        #   correct time (historical time from last event | or live time from system clock)

        return self._current_time

    def _process_events(self):
        """Main event processing loop - polls EventFeeds and distributes events."""
        while self._is_running:
            # Poll all EventFeeds for new events
            self._poll_event_feeds()

            # Process buffered events chronologically
            self._process_buffered_events()

            # Remove finished EventFeeds
            self._cleanup_finished_feeds()

            # Break if no more EventFeeds (for backtesting)
            if not self._event_feeds:
                break

    def _poll_event_feeds(self):
        """Poll all EventFeeds for new events and buffer them."""
        for feed in self._event_feeds:
            if feed.is_connected():
                event = feed.next()
                if event is not None:
                    # Add to buffer for chronological processing
                    heapq.heappush(self._event_buffer, event)
                    # TODO: Need to explain / understand, how this works really

    def _process_buffered_events(self):
        """Process buffered events in chronological order."""
        while self._event_buffer:
            # Get earliest event
            event = heapq.heappop(self._event_buffer)

            # Update current time
            self._current_time = event.dt_event

            # Distribute event via MessageBus
            self._distribute_event(event)

    def _distribute_event(self, event: Event):
        """Distribute event to strategies via MessageBus."""
        if event.event_type == "bar":
            topic = TopicProtocol.create_bar_topic(event.bar.bar_type)
            MessageBus.get().publish(topic, event)
        elif event.event_type == "trade_tick":
            topic = TopicProtocol.create_trade_tick_topic(event.trade_tick.instrument)
            MessageBus.get().publish(topic, event)
        elif event.event_type == "quote_tick":
            topic = TopicProtocol.create_quote_tick_topic(event.quote_tick.instrument)
            MessageBus.get().publish(topic, event)
        # Add other event types as needed

    def _cleanup_finished_feeds(self):
        """Remove finished EventFeeds to optimize performance."""
        finished_feeds = [feed for feed in self._event_feeds if feed.is_finished()]
        for feed in finished_feeds:
            feed.disconnect()
            self._event_feeds.remove(feed)

    def subscribe_to_bars(self, bar_type: BarType, subscriber: object):
        """Subscribe to bar data for the specified bar type.

        Args:
            bar_type (BarType): The type of bar to subscribe to.
            subscriber (object): The subscriber object (typically a strategy).

        Raises:
            RuntimeError: If no live data provider is configured.
        """
        if not self.live_data_provider:
            raise RuntimeError(
                f"Cannot call `subscribe_to_bars` for $bar_type ({bar_type}) because $live_data_provider is None. Set a live data provider when creating TradingEngine.",
            )
        self.live_data_provider.subscribe_to_bars(bar_type, subscriber)

    def unsubscribe_from_bars(self, bar_type: BarType, subscriber: object):
        """Unsubscribe from bar data for the specified bar type.

        Args:
            bar_type (BarType): The type of bar to unsubscribe from.
            subscriber (object): The subscriber object to remove.

        Raises:
            RuntimeError: If no live data provider is configured.
        """
        if not self.live_data_provider:
            raise RuntimeError(
                f"Cannot call `unsubscribe_from_bars` for $bar_type ({bar_type}) because $live_data_provider is None. Set a live data provider when creating TradingEngine.",
            )
        self.live_data_provider.unsubscribe_from_bars(bar_type, subscriber)

    def subscribe_to_trade_ticks(self, instrument: Instrument, subscriber: object):
        """Subscribe to trade tick data for the specified instrument.

        Args:
            instrument (Instrument): The instrument to subscribe to.
            subscriber (object): The subscriber object (typically a strategy).

        Raises:
            RuntimeError: If no live data provider is configured.
        """
        if not self.live_data_provider:
            raise RuntimeError(
                f"Cannot call `subscribe_to_trade_ticks` for $instrument ({instrument.name}) because $live_data_provider is None. Set a live data provider when creating TradingEngine.",
            )
        self.live_data_provider.subscribe_to_trade_ticks(instrument, subscriber)

    def unsubscribe_from_trade_ticks(self, instrument: Instrument, subscriber: object):
        """Unsubscribe from trade tick data for the specified instrument.

        Args:
            instrument (Instrument): The instrument to unsubscribe from.
            subscriber (object): The subscriber object to remove.

        Raises:
            RuntimeError: If no live data provider is configured.
        """
        if not self.live_data_provider:
            raise RuntimeError(
                f"Cannot call `unsubscribe_from_trade_ticks` for $instrument ({instrument.name}) because $live_data_provider is None. Set a live data provider when creating TradingEngine.",
            )
        self.live_data_provider.unsubscribe_from_trade_ticks(instrument, subscriber)

    def subscribe_to_quote_ticks(self, instrument: Instrument, subscriber: object):
        """Subscribe to quote tick data for the specified instrument.

        Args:
            instrument (Instrument): The instrument to subscribe to.
            subscriber (object): The subscriber object (typically a strategy).

        Raises:
            RuntimeError: If no live data provider is configured.
        """
        if not self.live_data_provider:
            raise RuntimeError(
                f"Cannot call `subscribe_to_quote_ticks` for $instrument ({instrument.name}) because $live_data_provider is None. Set a live data provider when creating TradingEngine.",
            )
        self.live_data_provider.subscribe_to_quote_ticks(instrument, subscriber)

    def unsubscribe_from_quote_ticks(self, instrument: Instrument, subscriber: object):
        """Unsubscribe from quote tick data for the specified instrument.

        Args:
            instrument (Instrument): The instrument to unsubscribe from.
            subscriber (object): The subscriber object to remove.

        Raises:
            RuntimeError: If no live data provider is configured.
        """
        if not self.live_data_provider:
            raise RuntimeError(
                f"Cannot call `unsubscribe_from_quote_ticks` for $instrument ({instrument.name}) because $live_data_provider is None. Set a live data provider when creating TradingEngine.",
            )
        self.live_data_provider.unsubscribe_from_quote_ticks(instrument, subscriber)

    def submit_order(self, order: Order):
        """Submit an order through the brokerage provider.

        Args:
            order (Order): The order to submit for execution.
        """
        self.brokerage_provider.submit_order(order)
