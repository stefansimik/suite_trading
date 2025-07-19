from typing import Protocol, Iterator, Optional, List, Dict, Any, Union
from datetime import datetime

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.instrument import Instrument

# Forward references for event types that will be implemented later
# These follow the same pattern as Bar (inherit from Event)
TradeTick = "TradeTick"
QuoteTick = "QuoteTick"


class MarketDataStorage(Protocol):
    """Storage interface for historical market data events.

    This interface provides a unified way to store and retrieve historical market data
    events for backtesting. It serves as the foundation for backtesting by providing
    historical events that match the same types used in live trading.

    The storage is designed to be implementation-neutral, supporting various backends
    like SQLite, PyArrow, files or cloud storage. All implementations must return
    the same Event objects used throughout the trading system.

    Key features:
    - Stores various market data types (bars, trade ticks, quote ticks)
    - Provides time-range queries for backtesting periods
    - Supports both single events and bulk operations
    - Handles connection management for database implementations
    - Returns Iterator for memory-efficient processing of large datasets

    Usage example:
        storage = SomeMarketDataStorage()
        storage.connect()

        # Get bars for backtesting
        bars = storage.get_bars(bar_type, start_date, end_date)
        for bar in bars:
            process_bar(bar)

        storage.disconnect()
    """

    def connect(self) -> None:
        """Connect to the storage backend.

        For database-based implementations, this establishes the connection to the
        database. For file-based implementations, this can be a no-op or handle
        file system preparation.

        Safe to call multiple times - should not reconnect if already connected.

        Raises:
            RuntimeError: If connection fails due to configuration or network issues.
        """
        ...

    def disconnect(self) -> None:
        """Disconnect from the storage backend and clean up resources.

        For database implementations, this closes the database connection.
        For file-based implementations, this handles cleanup of file handles
        or temporary resources.

        Safe to call multiple times - should not error if already disconnected.
        """
        ...

    def is_connected(self) -> bool:
        """Check if the storage is currently connected.

        For implementations that don't use connections (like simple file readers),
        this should return True when the storage is ready to use.

        Returns:
            bool: True if connected and ready to use, False otherwise.
        """
        ...

    def query_events(self, event_types: List[str], start: Optional[datetime] = None, end: Optional[datetime] = None) -> Iterator[Event]:
        """Get events of specified types within the given time range.

        This is the foundation method for all data retrieval. It returns events
        of the specified types within the time range, sorted chronologically.

        Args:
            event_types (List[str]): List of event type identifiers to retrieve.
                                   Examples: ["bar", "trade_tick", "quote_tick"]
            start (Optional[datetime]): Start of time range (inclusive).
                                      If None, no start limit is applied.
                                      Must be timezone-aware (UTC required).
            end (Optional[datetime]): End of time range (inclusive).
                                    If None, no end limit is applied.
                                    Must be timezone-aware (UTC required).

        Returns:
            Iterator[Event]: Iterator of events sorted by dt_event timestamp.
                           Returns events that match the specified types and
                           fall within the time range.

        Raises:
            RuntimeError: If storage is not connected when connection is required.
            ValueError: If event_types is empty or contains invalid type identifiers.
            ValueError: If start/end datetimes are not timezone-aware or start > end.

        Example:
            # Get all bars and trade ticks for a specific day
            events = storage.query_events(
                event_types=["bar", "trade_tick"],
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 1, 2, tzinfo=timezone.utc)
            )
            for event in events:
                process_event(event)
        """
        ...

    def get_bars(self, bar_type: BarType, start: Optional[datetime] = None, end: Optional[datetime] = None) -> Iterator[Bar]:
        """Get bar data for the specified bar type and time range.

        This is a user-friendly method built on top of query_events for the common
        use case of retrieving bars for backtesting.

        Args:
            bar_type (BarType): The specific bar type to retrieve (instrument,
                              period, price type combination).
            start (Optional[datetime]): Start of time range (inclusive).
                                      If None, returns all available bars from the beginning.
                                      Must be timezone-aware (UTC required).
            end (Optional[datetime]): End of time range (inclusive).
                                    If None, returns all available bars until the end.
                                    Must be timezone-aware (UTC required).

        Returns:
            Iterator[Bar]: Iterator of Bar objects sorted by dt_event timestamp.
                         Each Bar object contains OHLCV data and metadata.

        Raises:
            RuntimeError: If storage is not connected when connection is required.
            ValueError: If start/end datetimes are not timezone-aware or start > end.

        Example:
            # Get 1-minute EUR/USD bars for backtesting
            bar_type = BarType(eurusd_instrument, 1, BarUnit.MINUTE, PriceType.LAST)
            bars = storage.get_bars(
                bar_type=bar_type,
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 1, 31, tzinfo=timezone.utc)
            )
            for bar in bars:
                strategy.process_bar(bar)
        """
        ...

    def get_trade_ticks(self, instrument: Instrument, start: Optional[datetime] = None, end: Optional[datetime] = None) -> Iterator["TradeTick"]:
        """Get trade tick data for the specified instrument and time range.

        Trade ticks represent actual trades that occurred in the market,
        containing price, volume, and timing information.

        Args:
            instrument (Instrument): The financial instrument to retrieve trade ticks for.
            start (Optional[datetime]): Start of time range (inclusive).
                                      If None, returns all available ticks from the beginning.
                                      Must be timezone-aware (UTC required).
            end (Optional[datetime]): End of time range (inclusive).
                                    If None, returns all available ticks until the end.
                                    Must be timezone-aware (UTC required).

        Returns:
            Iterator[TradeTick]: Iterator of TradeTick objects sorted by dt_event timestamp.
                               Each TradeTick contains trade price, volume, and metadata.

        Raises:
            RuntimeError: If storage is not connected when connection is required.
            ValueError: If start/end datetimes are not timezone-aware or start > end.

        Example:
            # Get all EUR/USD trade ticks for a trading session
            ticks = storage.get_trade_ticks(
                instrument=eurusd_instrument,
                start=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
                end=datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)
            )
            for tick in ticks:
                strategy.process_trade_tick(tick)
        """
        ...

    def get_quote_ticks(self, instrument: Instrument, start: Optional[datetime] = None, end: Optional[datetime] = None) -> Iterator["QuoteTick"]:
        """Get quote tick data for the specified instrument and time range.

        Quote ticks represent bid/ask price updates from market makers,
        showing the best available prices for buying and selling.

        Args:
            instrument (Instrument): The financial instrument to retrieve quote ticks for.
            start (Optional[datetime]): Start of time range (inclusive).
                                      If None, returns all available quotes from the beginning.
                                      Must be timezone-aware (UTC required).
            end (Optional[datetime]): End of time range (inclusive).
                                    If None, returns all available quotes until the end.
                                    Must be timezone-aware (UTC required).

        Returns:
            Iterator[QuoteTick]: Iterator of QuoteTick objects sorted by dt_event timestamp.
                               Each QuoteTick contains bid/ask prices, sizes, and metadata.

        Raises:
            RuntimeError: If storage is not connected when connection is required.
            ValueError: If start/end datetimes are not timezone-aware or start > end.

        Example:
            # Get EUR/USD quote ticks for spread analysis
            quotes = storage.get_quote_ticks(
                instrument=eurusd_instrument,
                start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                end=datetime(2024, 1, 2, tzinfo=timezone.utc)
            )
            for quote in quotes:
                analyze_spread(quote.bid_price, quote.ask_price)
        """
        ...

    # TODO: This will need to be revisited in the future (it's just first proposal)
    def list_event_types(self) -> Dict[str, Dict[str, Any]]:
        """Get comprehensive information about all available event types and their data.

        This method provides discovery capabilities, allowing users to understand
        what data is available in the storage before querying specific events.

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping event type identifiers to
                                     their metadata. Each event type entry contains:
                                     - "start": earliest available datetime
                                     - "end": latest available datetime
                                     - "count": total number of events
                                     - "instruments": list of available instruments (for ticks)
                                     - "bar_types": list of available bar types (for bars)
                                     - Additional metadata specific to event type

        Raises:
            RuntimeError: If storage is not connected when connection is required.

        Example:
            metadata = storage.list_event_types()

            # Check available bar data
            if "bar" in metadata:
                bar_info = metadata["bar"]
                print(f"Bars available from {bar_info['start']} to {bar_info['end']}")
                print(f"Total bars: {bar_info['count']}")
                print(f"Available bar types: {bar_info['bar_types']}")

            # Check available trade tick data
            if "trade_tick" in metadata:
                tick_info = metadata["trade_tick"]
                print(f"Trade ticks for instruments: {tick_info['instruments']}")
        """
        ...

    def add_or_update(self, events: Union[Event, Iterator[Event]]) -> None:
        """Add new events or update existing events in the storage.

        This method handles both single event additions and bulk operations
        efficiently. If an event with the same key already exists, it will
        be updated with the new data.

        Args:
            events (Union[Event, Iterator[Event]]): Single event or iterator of events
                                                  to add or update. All events must be
                                                  timezone-aware (UTC required).

        Raises:
            RuntimeError: If storage is not connected when connection is required.
            RuntimeError: If storage is read-only and doesn't support modifications.
            ValueError: If events contain invalid data or non-UTC timestamps.

        Example:
            # Add single event
            storage.add_or_update(new_bar)

            # Bulk add from iterator
            storage.add_or_update(iter(bar_list))

            # Add events from generator
            def generate_bars():
                for i in range(1000):
                    yield create_bar(i)
            storage.add_or_update(generate_bars())
        """
        ...

    def remove(self, events: Union[Event, Iterator[Event]]) -> None:
        """Remove specified events from the storage.

        This method handles both single event removal and bulk operations
        efficiently. Events are identified by their unique characteristics
        (timestamp, instrument, event type, etc.).

        Args:
            events (Union[Event, Iterator[Event]]): Single event or iterator of events
                                                  to remove from storage.

        Raises:
            RuntimeError: If storage is not connected when connection is required.
            RuntimeError: If storage is read-only and doesn't support modifications.
            ValueError: If events contain invalid identification data.

        Example:
            # Remove single event
            storage.remove(outdated_bar)

            # Bulk remove from iterator
            storage.remove(iter(events_to_delete))
        """
        ...
