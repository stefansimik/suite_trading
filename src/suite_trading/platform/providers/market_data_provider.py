from abc import ABC, abstractmethod
from typing import Dict, Set, List
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.instrument import Instrument


class MarketDataProvider(ABC):
    """Abstract base class for market data providers with built-in subscription management.

    This class provides automatic subscription management by tracking actual subscriber objects,
    ensuring that data streams are started only when needed and stopped when no
    longer required by any strategy.

    Concrete implementations need only implement the abstract methods for actual
    data streaming operations.
    """

    def __init__(self):
        """Initialize the market data provider with subscription tracking."""
        self._subscriptions: Dict[BarType, Set[object]] = {}  # Subscriber objects per bar_type
        self._trade_tick_subscriptions: Dict[Instrument, Set[object]] = {}  # Subscriber objects per instrument
        self._quote_tick_subscriptions: Dict[Instrument, Set[object]] = {}  # Subscriber objects per instrument

    # Subscription management (provided by base class)
    def subscribe_to_bars(self, bar_type: BarType, subscriber: object) -> None:
        """Subscribe to bars with automatic subscriber tracking and stream management.

        Args:
            bar_type (BarType): The type of bar to subscribe to.
            subscriber (object): The subscriber object (typically a strategy).

        Raises:
            ConnectionError: If not connected to market data source.
        """
        subscribers = self._subscriptions.get(bar_type, set())
        was_empty = len(subscribers) == 0

        # Add the subscriber to the set
        subscribers.add(subscriber)
        self._subscriptions[bar_type] = subscribers

        # Start publishing if this is the first subscriber
        if was_empty:
            self._start_publishing_bars(bar_type)

    def unsubscribe_from_bars(self, bar_type: BarType, subscriber: object) -> None:
        """Unsubscribe from bars with automatic cleanup.

        Args:
            bar_type (BarType): The type of bar to unsubscribe from.
            subscriber (object): The subscriber object to remove.
        """
        subscribers = self._subscriptions.get(bar_type, set())
        if subscriber in subscribers:
            subscribers.remove(subscriber)

            if len(subscribers) == 0:
                # Last subscriber - stop publishing and remove the bar_type
                self._subscriptions.pop(bar_type, None)
                self._stop_publishing_bars(bar_type)
            else:
                # Update the subscribers set
                self._subscriptions[bar_type] = subscribers

    def subscribe_to_trade_ticks(self, instrument: Instrument, subscriber: object) -> None:
        """Subscribe to trade ticks with automatic subscriber tracking and stream management.

        Args:
            instrument (Instrument): The instrument to subscribe to.
            subscriber (object): The subscriber object (typically a strategy).

        Raises:
            ConnectionError: If not connected to market data source.
        """
        subscribers = self._trade_tick_subscriptions.get(instrument, set())
        was_empty = len(subscribers) == 0

        # Add the subscriber to the set
        subscribers.add(subscriber)
        self._trade_tick_subscriptions[instrument] = subscribers

        # Start publishing if this is the first subscriber
        if was_empty:
            self._start_publishing_trade_ticks(instrument)

    def unsubscribe_from_trade_ticks(self, instrument: Instrument, subscriber: object) -> None:
        """Unsubscribe from trade ticks with automatic cleanup.

        Args:
            instrument (Instrument): The instrument to unsubscribe from.
            subscriber (object): The subscriber object to remove.
        """
        subscribers = self._trade_tick_subscriptions.get(instrument, set())
        if subscriber in subscribers:
            subscribers.remove(subscriber)

            if len(subscribers) == 0:
                # Last subscriber - stop publishing and remove the instrument
                self._trade_tick_subscriptions.pop(instrument, None)
                self._stop_publishing_trade_ticks(instrument)
            else:
                # Update the subscribers set
                self._trade_tick_subscriptions[instrument] = subscribers

    def subscribe_to_quote_ticks(self, instrument: Instrument, subscriber: object) -> None:
        """Subscribe to quote ticks with automatic subscriber tracking and stream management.

        Args:
            instrument (Instrument): The instrument to subscribe to.
            subscriber (object): The subscriber object (typically a strategy).

        Raises:
            ConnectionError: If not connected to market data source.
        """
        subscribers = self._quote_tick_subscriptions.get(instrument, set())
        was_empty = len(subscribers) == 0

        # Add the subscriber to the set
        subscribers.add(subscriber)
        self._quote_tick_subscriptions[instrument] = subscribers

        # Start publishing if this is the first subscriber
        if was_empty:
            self._start_publishing_quote_ticks(instrument)

    def unsubscribe_from_quote_ticks(self, instrument: Instrument, subscriber: object) -> None:
        """Unsubscribe from quote ticks with automatic cleanup.

        Args:
            instrument (Instrument): The instrument to unsubscribe from.
            subscriber (object): The subscriber object to remove.
        """
        subscribers = self._quote_tick_subscriptions.get(instrument, set())
        if subscriber in subscribers:
            subscribers.remove(subscriber)

            if len(subscribers) == 0:
                # Last subscriber - stop publishing and remove the instrument
                self._quote_tick_subscriptions.pop(instrument, None)
                self._stop_publishing_quote_ticks(instrument)
            else:
                # Update the subscribers set
                self._quote_tick_subscriptions[instrument] = subscribers

    # Connection management (abstract - must be implemented)
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to market data source.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to market data source.

        Should handle cases where connection is already closed gracefully.
        """
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status.

        Returns:
            bool: True if connected to market data source, False otherwise.
        """
        ...

    # Data retrieval (abstract - must be implemented)
    @abstractmethod
    def get_historical_data(self, bar_type: BarType, count: int) -> List[Bar]:
        """Retrieve last N bars/ticks before current time for specified bar type.

        Args:
            bar_type (BarType): The type of bar to retrieve.
            count (int): Number of historical bars to retrieve.

        Returns:
            List[Bar]: List of historical bars, ordered from oldest to newest.

        Raises:
            ValueError: If count is not positive.
            ConnectionError: If not connected to market data source.
        """
        ...

    # Streaming methods (abstract - must be implemented)
    @abstractmethod
    def _start_publishing_bars(self, bar_type: BarType) -> None:
        """Start the actual data stream for this bar type.

        This method is called internally when the first subscriber requests data.
        Concrete implementations should start the actual data streaming here.

        Args:
            bar_type (BarType): The type of bar to start publishing.

        Raises:
            ConnectionError: If not connected to market data source.
        """
        ...

    @abstractmethod
    def _stop_publishing_bars(self, bar_type: BarType) -> None:
        """Stop the actual data stream for this bar type.

        This method is called internally when the last subscriber unsubscribes.
        Concrete implementations should stop the actual data streaming here.

        Args:
            bar_type (BarType): The type of bar to stop publishing.
        """
        ...

    @abstractmethod
    def _start_publishing_trade_ticks(self, instrument: Instrument) -> None:
        """Start the actual trade tick stream for this instrument.

        This method is called internally when the first subscriber requests data.
        Concrete implementations should start the actual trade tick streaming here.

        Args:
            instrument (Instrument): The instrument to start publishing trade ticks for.

        Raises:
            ConnectionError: If not connected to market data source.
        """
        ...

    @abstractmethod
    def _stop_publishing_trade_ticks(self, instrument: Instrument) -> None:
        """Stop the actual trade tick stream for this instrument.

        This method is called internally when the last subscriber unsubscribes.
        Concrete implementations should stop the actual trade tick streaming here.

        Args:
            instrument (Instrument): The instrument to stop publishing trade ticks for.
        """
        ...

    @abstractmethod
    def _start_publishing_quote_ticks(self, instrument: Instrument) -> None:
        """Start the actual quote tick stream for this instrument.

        This method is called internally when the first subscriber requests data.
        Concrete implementations should start the actual quote tick streaming here.

        Args:
            instrument (Instrument): The instrument to start publishing quote ticks for.

        Raises:
            ConnectionError: If not connected to market data source.
        """
        ...

    @abstractmethod
    def _stop_publishing_quote_ticks(self, instrument: Instrument) -> None:
        """Stop the actual quote tick stream for this instrument.

        This method is called internally when the last subscriber unsubscribes.
        Concrete implementations should stop the actual quote tick streaming here.

        Args:
            instrument (Instrument): The instrument to stop publishing quote ticks for.
        """
        ...
