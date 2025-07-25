"""Market data provider protocol definition."""

from datetime import datetime
from typing import Optional, Protocol, Sequence

from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType

# TODO: Specify callbacks invoked in Strategy, if methods below are called


class MarketDataProvider(Protocol):
    """Protocol for market data providers.

    Defines the interface for retrieving historical market data and
    subscribing to live market data streams.
    """

    def connect(self) -> None:
        """Establish market data provider connection.

        Connects to the market data source to enable data retrieval and
        subscription capabilities. Must be called before requesting any data.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        ...

    def disconnect(self) -> None:
        """Close market data provider connection.

        Cleanly disconnects from the market data source and stops all active
        subscriptions. Handles cases where connection is already closed gracefully.
        """
        ...

    def is_connected(self) -> bool:
        """Check market data provider connection status.

        Returns:
            bool: True if connected to market data provider, False otherwise.
        """
        ...

    def get_historical_bars_series(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: Optional[datetime] = None,
    ) -> Sequence[Bar]:
        """Get all historical bars at once for strategy initialization and analysis.

        Returns complete historical dataset as a sequence, perfect for setting up
        indicators, calculating initial values, or analyzing patterns that need
        the full dataset available immediately.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
            from_dt: Start datetime for the data range.
            until_dt: End datetime for the data range. If None, gets data
                     until the latest available.

        Returns:
            Sequence of Bar objects containing historical market data.
        """
        ...

    def stream_historical_bars(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: Optional[datetime] = None,
    ) -> None:
        """Stream historical bars one-by-one for memory-efficient backtesting.

        Delivers bars individually through callbacks, perfect for processing
        large historical datasets without loading everything into memory at once.
        Maintains chronological order just like live trading scenarios.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
            from_dt: Start datetime for the data range.
            until_dt: End datetime for the data range. If None, streams data
                     until the latest available.
        """
        ...

    def subscribe_to_live_bars(
        self,
        bar_type: BarType,
    ) -> None:
        """Subscribe to real-time bar data feed for live trading.

        Starts receiving live market data as it happens, allowing strategies
        to react to current market conditions. Can be called dynamically
        during strategy execution to adapt data needs based on runtime conditions.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
        """
        ...

    def subscribe_to_live_bars_with_history(
        self,
        bar_type: BarType,
        history_days: int,
    ) -> None:
        """Subscribe to live bars with seamless historical-to-live transition.

        First feeds historical bars for the specified number of days before now,
        then automatically starts feeding live bars without any gaps between
        historical and live data. This ensures continuous data flow with no missing
        bars, critical for live trading scenarios that need recent historical context.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
            history_days: Number of days before now to include historical data.
        """
        ...

    def unsubscribe_from_live_bars(
        self,
        bar_type: BarType,
    ) -> None:
        """Stop receiving live bar updates for an instrument.

        Cancels active subscription and stops the flow of live market data.
        Useful for strategies that need to dynamically adjust their data
        subscriptions based on changing market conditions or trading logic.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
        """
        ...
