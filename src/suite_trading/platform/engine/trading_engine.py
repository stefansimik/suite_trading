import logging
from suite_trading.strategy.base import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.topic_protocol import TopicProtocol
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.instrument import Instrument

logger = logging.getLogger(__name__)


class TradingEngine:
    """Simple engine for managing and running trading strategies.

    The TradingEngine coordinates strategies and provides a framework for strategy
    execution and management.

    **Architecture:**
    - **Strategies**: Implement trading logic and subscribe to events via MessageBus
    - **MessageBus**: Handles event distribution to strategies

    This simple design focuses on strategy coordination and management.
    """

    def __init__(self):
        """Initialize a new TradingEngine instance.

        Creates its own MessageBus instance for isolated operation.
        """
        self.strategies: list[Strategy] = []
        self._is_running: bool = False
        self.message_bus = MessageBus()

        # Track strategy subscriptions for demand-based publishing
        self._bar_subscriptions: dict[BarType, set[Strategy]] = {}  # Track which strategies subscribe to which bar types
        self._trade_tick_subscriptions: dict[Instrument, set[Strategy]] = {}  # Track trade tick subscriptions
        self._quote_tick_subscriptions: dict[Instrument, set[Strategy]] = {}  # Track quote tick subscriptions

    def start(self):
        """Start the TradingEngine and all strategies.

        This method starts all registered strategies.
        """
        self._is_running = True

        # Start strategies
        for strategy in self.strategies:
            strategy.on_start()

    def stop(self):
        """Stop the TradingEngine and all strategies.

        This method stops all registered strategies.
        """
        self._is_running = False

        # Stop strategies
        for strategy in self.strategies:
            strategy.on_stop()

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

    # -----------------------------------------------
    # MARKET DATA SUBSCRIPTION MANAGEMENT
    # -----------------------------------------------

    def subscribe_to_bars(self, bar_type: BarType, strategy: Strategy):
        """Subscribe a strategy to bar data for a specific bar type.

        This method handles all the technical details of subscription:
        - Subscribes the strategy to the MessageBus topic
        - Tracks which strategies are subscribed to which bar types
        - Initiates data publishing when first strategy subscribes

        Args:
            bar_type (BarType): The type of bar to subscribe to.
            strategy (Strategy): The strategy that wants to subscribe.
        """
        # Initialize subscription set for this bar type if needed
        if bar_type not in self._bar_subscriptions:
            self._bar_subscriptions[bar_type] = set()

        # Check if this is the first subscriber for this bar type
        is_first_subscriber = len(self._bar_subscriptions[bar_type]) == 0

        # Add strategy to subscription tracking
        self._bar_subscriptions[bar_type].add(strategy)

        # Subscribe strategy to MessageBus topic
        topic = TopicProtocol.create_bar_topic(bar_type)
        self.message_bus.subscribe(topic, strategy.on_event)

        # TODO: Initiate sending bars from market data provider
        # When first strategy subscribes, start requesting this bar type from data provider
        if is_first_subscriber:
            # TODO: self.market_data_provider.start_bars(bar_type)
            pass

    def unsubscribe_from_bars(self, bar_type: BarType, strategy: Strategy):
        """Unsubscribe a strategy from bar data for a specific bar type.

        This method handles cleanup when a strategy unsubscribes:
        - Unsubscribes the strategy from the MessageBus topic
        - Removes strategy from subscription tracking
        - Stops data publishing when last strategy unsubscribes

        Args:
            bar_type (BarType): The type of bar to unsubscribe from.
            strategy (Strategy): The strategy that wants to unsubscribe.
        """
        # Check if we have subscriptions for this bar type
        if bar_type not in self._bar_subscriptions:
            logger.warning(
                f"Cannot call `unsubscribe_from_bars` for $bar_type ({bar_type}) and $strategy ('{strategy.name}') because no subscriptions exist for this bar type. This likely indicates a logical mistake - trying to unsubscribe from something that was never subscribed to.",
            )
            return

        # Remove strategy from subscription tracking
        self._bar_subscriptions[bar_type].discard(strategy)

        # Unsubscribe strategy from MessageBus topic
        topic = TopicProtocol.create_bar_topic(bar_type)
        self.message_bus.unsubscribe(topic, strategy.on_event)

        # Check if this was the last subscriber
        if len(self._bar_subscriptions[bar_type]) == 0:
            # Clean up empty subscription set
            del self._bar_subscriptions[bar_type]

            # TODO: Stop requesting bars from market data provider
            # When last strategy unsubscribes, stop requesting this bar type from data provider
            # TODO: self.market_data_provider.stop_bars(bar_type)
            pass

    def subscribe_to_trade_ticks(self, instrument: Instrument, strategy: Strategy):
        """Subscribe a strategy to trade tick data for a specific instrument.

        This method handles all the technical details of subscription:
        - Subscribes the strategy to the MessageBus topic
        - Tracks which strategies are subscribed to which instruments
        - Initiates data publishing when first strategy subscribes

        Args:
            instrument (Instrument): The instrument to subscribe to.
            strategy (Strategy): The strategy that wants to subscribe.
        """
        # Initialize subscription set for this instrument if needed
        if instrument not in self._trade_tick_subscriptions:
            self._trade_tick_subscriptions[instrument] = set()

        # Check if this is the first subscriber for this instrument
        is_first_subscriber = len(self._trade_tick_subscriptions[instrument]) == 0

        # Add strategy to subscription tracking
        self._trade_tick_subscriptions[instrument].add(strategy)

        # Subscribe strategy to MessageBus topic
        topic = TopicProtocol.create_trade_tick_topic(instrument)
        self.message_bus.subscribe(topic, strategy.on_event)

        # TODO: Initiate sending trade ticks from market data provider
        # When first strategy subscribes, start requesting this instrument from data provider
        if is_first_subscriber:
            # TODO: self.market_data_provider.start_trade_ticks(instrument)
            pass

    def unsubscribe_from_trade_ticks(self, instrument: Instrument, strategy: Strategy):
        """Unsubscribe a strategy from trade tick data for a specific instrument.

        This method handles cleanup when a strategy unsubscribes:
        - Unsubscribes the strategy from the MessageBus topic
        - Removes strategy from subscription tracking
        - Stops data publishing when last strategy unsubscribes

        Args:
            instrument (Instrument): The instrument to unsubscribe from.
            strategy (Strategy): The strategy that wants to unsubscribe.
        """
        # Check if we have subscriptions for this instrument
        if instrument not in self._trade_tick_subscriptions:
            logger.warning(
                f"Cannot call `unsubscribe_from_trade_ticks` for $instrument ({instrument}) and $strategy ('{strategy.name}') because no subscriptions exist for this instrument. This likely indicates a logical mistake - trying to unsubscribe from something that was never subscribed to.",
            )
            return

        # Remove strategy from subscription tracking
        self._trade_tick_subscriptions[instrument].discard(strategy)

        # Unsubscribe strategy from MessageBus topic
        topic = TopicProtocol.create_trade_tick_topic(instrument)
        self.message_bus.unsubscribe(topic, strategy.on_event)

        # Check if this was the last subscriber
        if len(self._trade_tick_subscriptions[instrument]) == 0:
            # Clean up empty subscription set
            del self._trade_tick_subscriptions[instrument]

            # TODO: Stop requesting trade ticks from market data provider
            # When last strategy unsubscribes, stop requesting this instrument from data provider
            # TODO: self.market_data_provider.stop_trade_ticks(instrument)
            pass

    def subscribe_to_quote_ticks(self, instrument: Instrument, strategy: Strategy):
        """Subscribe a strategy to quote tick data for a specific instrument.

        This method handles all the technical details of subscription:
        - Subscribes the strategy to the MessageBus topic
        - Tracks which strategies are subscribed to which instruments
        - Initiates data publishing when first strategy subscribes

        Args:
            instrument (Instrument): The instrument to subscribe to.
            strategy (Strategy): The strategy that wants to subscribe.
        """
        # Initialize subscription set for this instrument if needed
        if instrument not in self._quote_tick_subscriptions:
            self._quote_tick_subscriptions[instrument] = set()

        # Check if this is the first subscriber for this instrument
        is_first_subscriber = len(self._quote_tick_subscriptions[instrument]) == 0

        # Add strategy to subscription tracking
        self._quote_tick_subscriptions[instrument].add(strategy)

        # Subscribe strategy to MessageBus topic
        topic = TopicProtocol.create_quote_tick_topic(instrument)
        self.message_bus.subscribe(topic, strategy.on_event)

        # TODO: Initiate sending quote ticks from market data provider
        # When first strategy subscribes, start requesting this instrument from data provider
        if is_first_subscriber:
            # TODO: self.market_data_provider.start_quote_ticks(instrument)
            pass

    def unsubscribe_from_quote_ticks(self, instrument: Instrument, strategy: Strategy):
        """Unsubscribe a strategy from quote tick data for a specific instrument.

        This method handles cleanup when a strategy unsubscribes:
        - Unsubscribes the strategy from the MessageBus topic
        - Removes strategy from subscription tracking
        - Stops data publishing when last strategy unsubscribes

        Args:
            instrument (Instrument): The instrument to unsubscribe from.
            strategy (Strategy): The strategy that wants to unsubscribe.
        """
        # Check if we have subscriptions for this instrument
        if instrument not in self._quote_tick_subscriptions:
            logger.warning(
                f"Cannot call `unsubscribe_from_quote_ticks` for $instrument ({instrument}) and $strategy ('{strategy.name}') because no subscriptions exist for this instrument. This likely indicates a logical mistake - trying to unsubscribe from something that was never subscribed to.",
            )
            return

        # Remove strategy from subscription tracking
        self._quote_tick_subscriptions[instrument].discard(strategy)

        # Unsubscribe strategy from MessageBus topic
        topic = TopicProtocol.create_quote_tick_topic(instrument)
        self.message_bus.unsubscribe(topic, strategy.on_event)

        # Check if this was the last subscriber
        if len(self._quote_tick_subscriptions[instrument]) == 0:
            # Clean up empty subscription set
            del self._quote_tick_subscriptions[instrument]

            # TODO: Stop requesting quote ticks from market data provider
            # When last strategy unsubscribes, stop requesting this instrument from data provider
            # TODO: self.market_data_provider.stop_quote_ticks(instrument)
            pass
