from abc import ABC, abstractmethod
from typing import List
from datetime import datetime
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar import Bar


class HistoricalMarketDataProvider(ABC):
    """Abstract base class for historical market data providers.

    This provider focuses solely on efficient bulk historical data retrieval.
    It handles synchronous, one-time operations for fetching historical market data
    that strategies need for initialization, analysis, or backtesting.

    The provider is designed to be simple and focused - it doesn't handle
    subscriptions, streaming, or real-time data. For live data streaming,
    use LiveMarketDataProvider instead.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to historical data source.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to historical data source.

        Should handle cases where connection is already closed gracefully.
        """
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status.

        Returns:
            bool: True if connected to historical data source, False otherwise.
        """
        ...

    @abstractmethod
    def get_historical_bars(self, bar_type: BarType, count: int) -> List[Bar]:
        """Retrieve last N bars before current time for specified bar type.

        Args:
            bar_type (BarType): The type of bar to retrieve.
            count (int): Number of historical bars to retrieve.

        Returns:
            List[Bar]: List of historical bars, ordered from oldest to newest.

        Raises:
            ValueError: If count is not positive.
            ConnectionError: If not connected to historical data source.
        """
        ...

    @abstractmethod
    def get_historical_bars_range(self, bar_type: BarType, start: datetime, end: datetime) -> List[Bar]:
        """Retrieve historical bars for specified date range.

        Args:
            bar_type (BarType): The type of bar to retrieve.
            start (datetime): Start date/time for the range (inclusive).
            end (datetime): End date/time for the range (inclusive).

        Returns:
            List[Bar]: List of historical bars within the range, ordered from oldest to newest.

        Raises:
            ValueError: If start date is after end date.
            ConnectionError: If not connected to historical data source.
        """
        ...
