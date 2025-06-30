import logging
from suite_trading.strategy.base import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.message_priority import SubscriberPriority
from suite_trading.platform.messaging.topic_protocol import TopicProtocol
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.platform.cache import Cache

logger = logging.getLogger(__name__)


class TradingEngine:
    """Main engine for managing and running trading strategies.

    The TradingEngine is responsible for managing the lifecycle of strategies,
    ensuring they have unique names, and coordinating their execution.
    """

    def __init__(self):
        """Initialize a new TradingEngine instance.

        Creates a Cache component internally. Uses the singleton MessageBus instance.
        """
        self.strategies: list[Strategy] = []
        self._cache = Cache()

        # Subscribe cache to all bar data with highest priority
        self._setup_cache_subscriptions()

    @property
    def cache(self) -> Cache:
        """Get the cache instance.

        Returns:
            Cache: The cache instance.
        """
        return self._cache

    def _setup_cache_subscriptions(self):
        """Set up cache subscriptions with system highest priority.

        This ensures the cache receives and stores data before strategies process it.
        """
        # Subscribe to the wildcard topic to catch all bars with system highest priority
        MessageBus.get().subscribe("bar::*", self._cache.on_bar, SubscriberPriority.SYSTEM_HIGHEST)

    def start(self):
        """Start all registered strategies.

        This method calls the on_start method of each registered strategy.
        """
        for strategy in self.strategies:
            strategy.on_start()

    def stop(self):
        """Stop all registered strategies.

        This method calls the on_stop method of each registered strategy,
        which will automatically unsubscribe from all bar subscriptions.
        """
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
