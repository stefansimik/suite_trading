import logging
from datetime import datetime
from typing import Dict, List
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.platform.messaging.topic_factory import TopicFactory
from suite_trading.platform.market_data.market_data_provider import MarketDataProvider
from suite_trading.platform.broker.broker import Broker
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.order.orders import Order

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

    # region Initialize engine

    def __init__(self):
        """Initialize a new TradingEngine instance.

        Creates its own MessageBus instance for isolated operation.
        """
        # Engine state and core components
        self._is_running: bool = False
        self.message_bus = MessageBus()

        # Strategy management
        self._strategies: Dict[str, Strategy] = {}

        # Market data provider management
        self._market_data_providers: Dict[str, MarketDataProvider] = {}

        # Broker management
        self._brokers: Dict[str, Broker] = {}

    # endregion

    # region Start and stop engine

    def start(self):
        """Start the TradingEngine and all strategies.

        This method starts all registered strategies.
        """
        self._is_running = True

        # Start strategies
        for strategy in self._strategies.values():
            strategy.on_start()

    def stop(self):
        """Stop the TradingEngine and all strategies.

        This method stops all registered strategies.
        """
        self._is_running = False

        # Stop strategies
        for strategy in self._strategies.values():
            strategy.on_stop()

    # endregion

    # region Manage strategies

    def add_strategy(self, strategy: Strategy) -> None:
        """Register a strategy using its unique name.

        Args:
            strategy: The strategy instance to register.

        Raises:
            ValueError: If a strategy with the same name already exists.
        """
        name = strategy.get_unique_name()

        if name in self._strategies:
            raise ValueError(f"Strategy with $name '{name}' already exists. Cannot add another strategy with the same name.")

        # Set the trading engine reference in the strategy
        strategy._set_trading_engine(self)
        self._strategies[name] = strategy

    def remove_strategy(self, strategy: Strategy) -> None:
        """Remove a strategy using its unique name.

        Args:
            strategy: The strategy instance to remove.

        Raises:
            KeyError: If no strategy with the given name exists.
        """
        name = strategy.get_unique_name()

        if name not in self._strategies:
            raise KeyError(f"No strategy with $name '{name}' is registered. Cannot remove non-existent strategy.")

        # Remove from strategies dictionary
        del self._strategies[name]

    @property
    def strategies(self) -> Dict[str, Strategy]:
        """Get all registered strategies.

        Returns:
            Dictionary mapping strategy names to strategy instances.
        """
        return self._strategies

    # endregion

    # region Manage market data providers

    def add_market_data_provider(self, provider: MarketDataProvider) -> None:
        """Register a market data provider using its unique name.

        Args:
            provider: The market data provider instance to register.

        Raises:
            ValueError: If a provider with the same name already exists.
        """
        name = provider.get_unique_name()

        if name in self._market_data_providers:
            raise ValueError(f"Provider with $name '{name}' already exists. Cannot add another provider with the same name.")

        self._market_data_providers[name] = provider

    def remove_market_data_provider(self, provider: MarketDataProvider) -> None:
        """Remove a market data provider using its unique name.

        Args:
            provider: The market data provider instance to remove.

        Raises:
            KeyError: If no provider with the given name exists.
        """
        name = provider.get_unique_name()

        if name not in self._market_data_providers:
            raise KeyError(f"No market data provider with $name '{name}' is registered. Cannot remove non-existent provider.")

        del self._market_data_providers[name]

    @property
    def market_data_providers(self) -> Dict[str, MarketDataProvider]:
        """Get all registered market data providers.

        Returns:
            Dictionary mapping provider names to provider instances.
        """
        return self._market_data_providers

    # endregion

    # region Manage brokers

    def add_broker(self, broker: Broker) -> None:
        """Register a broker using its unique name.

        Args:
            broker: The broker instance to register.

        Raises:
            ValueError: If a broker with the same name already exists.
        """
        name = broker.get_unique_name()

        if name in self._brokers:
            raise ValueError(f"Broker with $name '{name}' already exists. Cannot add another broker with the same name.")

        self._brokers[name] = broker

    def remove_broker(self, broker: Broker) -> None:
        """Remove a broker using its unique name.

        Args:
            broker: The broker instance to remove.

        Raises:
            KeyError: If no broker with the given name exists.
        """
        name = broker.get_unique_name()

        if name not in self._brokers:
            raise KeyError(f"No broker with $name '{name}' is registered. Cannot remove non-existent broker.")

        del self._brokers[name]

    @property
    def brokers(self) -> Dict[str, Broker]:
        """Get all registered brokers.

        Returns:
            Dictionary mapping broker names to broker instances.
        """
        return self._brokers

    # endregion

    # region Helper methods

    def publish_bar(self, bar: Bar, is_historical: bool = True) -> None:
        """Publish a bar to the MessageBus for distribution to subscribed strategies.

        Creates a NewBarEvent with the specified historical context and publishes it to the appropriate topic.

        Args:
            bar: The bar to publish.
            is_historical: Whether this bar data is historical or live. Defaults to True.
        """
        event = NewBarEvent(bar=bar, dt_received=datetime.now(), is_historical=is_historical)
        topic = TopicFactory.create_topic_for_bar(bar.bar_type)
        self.message_bus.publish(topic, event)

    # endregion

    # region Submit orders

    def submit_order(self, order: Order, broker: Broker) -> None:
        """Submit an order through the specified broker.

        Args:
            order: The order to submit.
            broker: The broker to submit the order through.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order is invalid or cannot be submitted.
        """
        broker.submit_order(order)

    def cancel_order(self, order: Order, broker: Broker) -> None:
        """Cancel an order through the specified broker.

        Args:
            order: The order to cancel.
            broker: The broker to cancel the order through.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order cannot be cancelled.
        """
        broker.cancel_order(order)

    def modify_order(self, order: Order, broker: Broker) -> None:
        """Modify an order through the specified broker.

        Args:
            order: The order to modify with updated parameters.
            broker: The broker to modify the order through.

        Raises:
            ConnectionError: If the broker is not connected.
            ValueError: If the order cannot be modified.
        """
        broker.modify_order(order)

    def get_active_orders(self, broker: Broker) -> List[Order]:
        """Get all active orders from the specified broker.

        Args:
            broker: The broker to get active orders from.

        Returns:
            List of all active orders for the specified broker.

        Raises:
            ConnectionError: If the broker is not connected.
        """
        return broker.get_active_orders()

    # endregion
