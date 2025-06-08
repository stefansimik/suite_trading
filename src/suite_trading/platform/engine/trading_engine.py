import logging
from suite_trading.strategy.base import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.topic_protocol import TopicProtocol
from suite_trading.domain.market_data.bar import Bar

logger = logging.getLogger(__name__)


class TradingEngine:
    """Main engine for managing and running trading strategies.

    The TradingEngine is responsible for managing the lifecycle of strategies,
    ensuring they have unique names, and coordinating their execution.
    """

    def __init__(self):
        """Initialize a new TradingEngine instance.

        Creates a new MessageBus instance internally.
        """
        self.strategies: list[Strategy] = []
        self._message_bus = MessageBus()

    @property
    def message_bus(self) -> MessageBus:
        """Get the message bus instance.

        Returns:
            MessageBus: The message bus instance.
        """
        return self._message_bus

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
        """
        # Create a standardized topic name for the bar
        topic = TopicProtocol.create_bar_topic(bar.bar_type)

        # Publish the bar to the message bus
        self._message_bus.publish(topic, bar)
