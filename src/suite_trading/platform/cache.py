from typing import Dict, List, Optional
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType


class Cache:
    """In-memory storage for all market data with fast access patterns optimized for trading strategies.

    The Cache stores market data in memory and provides simple access methods for strategies.
    Data is stored with newest items first (index 0 = latest).
    """

    def __init__(self):
        """Initialize a new Cache instance.

        Creates empty storage for bars. Future extensions will include
        trade ticks, quote ticks, and orders.
        """
        # Bar storage: BarType -> List[Bar] (newest first, index 0 = latest)
        self._bars: Dict[BarType, List[Bar]] = {}

        # Future extensions (not implemented now):
        # self._trade_ticks: Dict[Instrument, List[TradeTick]] = {}
        # self._quote_ticks: Dict[Instrument, List[QuoteTick]] = {}
        # self._orders: Dict[str, Order] = {}  # order_id -> Order

    def on_bar(self, bar: Bar):
        """Handle incoming bar data by storing it in the cache.

        This method is called by the MessageBus when new bar data arrives.
        Bars are stored with newest first (index 0 = latest).

        Args:
            bar (Bar): The bar data to store.
        """
        if bar.bar_type not in self._bars:
            self._bars[bar.bar_type] = []

        # Insert at the beginning to maintain newest-first order
        self._bars[bar.bar_type].insert(0, bar)

    def bars(self, bar_type: BarType, count: Optional[int] = None) -> List[Bar]:
        """Get bars for a specific bar type.

        Args:
            bar_type (BarType): The type of bar to retrieve.
            count (Optional[int]): Maximum number of bars to return. If None, returns all bars.

        Returns:
            List[Bar]: List of bars, newest first (index 0 = latest).
        """
        if bar_type not in self._bars:
            return []

        bars_list = self._bars[bar_type]

        if count is None:
            return bars_list.copy()
        else:
            return bars_list[:count]

    def last_bar(self, bar_type: BarType) -> Optional[Bar]:
        """Get the last bar for a specific bar type.

        Args:
            bar_type (BarType): The type of bar to retrieve.

        Returns:
            Optional[Bar]: The latest bar, or None if no bars exist.
        """
        if bar_type not in self._bars or not self._bars[bar_type]:
            return None

        return self._bars[bar_type][0]

    def has_bars(self, bar_type: BarType) -> bool:
        """Check if bars exist for a specific bar type.

        Args:
            bar_type (BarType): The type of bar to check.

        Returns:
            bool: True if bars exist, False otherwise.
        """
        return bar_type in self._bars and len(self._bars[bar_type]) > 0

    def bar_count(self, bar_type: BarType) -> int:
        """Get the number of bars stored for a specific bar type.

        Args:
            bar_type (BarType): The type of bar to count.

        Returns:
            int: The number of bars stored.
        """
        if bar_type not in self._bars:
            return 0

        return len(self._bars[bar_type])
