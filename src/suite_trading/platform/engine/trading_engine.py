import logging
from typing import Optional
from suite_trading.strategy.base import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.message_priority import SubscriberPriority
from suite_trading.platform.messaging.topic_protocol import TopicProtocol
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order import Order
from suite_trading.platform.cache import Cache
from suite_trading.platform.providers.historical_market_data_provider import HistoricalMarketDataProvider
from suite_trading.platform.providers.live_market_data_provider import LiveMarketDataProvider
from suite_trading.platform.providers.brokerage_provider import BrokerageProvider

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

        # Subscribe cache to all bar data with system highest priority
        # This ensures the cache receives and stores data before strategies process it
        MessageBus.get().subscribe("bar::*", Cache.get().on_bar, SubscriberPriority.SYSTEM_HIGHEST)

    def start(self):
        """Start all registered strategies and connect providers.

        This method connects the providers and calls the on_start
        method of each registered strategy.
        """
        # Connect providers
        if self.historical_data_provider:
            self.historical_data_provider.connect()
        if self.live_data_provider:
            self.live_data_provider.connect()
        self.brokerage_provider.connect()

        # Start strategies
        for strategy in self.strategies:
            strategy.on_start()

    def stop(self):
        """Stop all strategies and disconnect providers.

        This method calls the on_stop method of each registered strategy,
        which will automatically unsubscribe from all bar subscriptions,
        then disconnects the providers.
        """
        # Stop strategies first
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

    # TODO: This will be removed and replaced by MarketDataProvider functionality
    def publish_bar(self, bar: Bar):
        """Publish a bar to the message bus.

        Args:
            bar (Bar): The bar to publish.

        Raises:
            ValueError: If no strategies are subscribed to receive the bar data.
        """
        # Create a standardized topic name for the bar
        topic = TopicProtocol.create_bar_topic(bar.bar_type)

        # Publish the bar to the message bus
        MessageBus.get().publish(topic, bar)
