from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.event import Event
    from suite_trading.domain.market_data.order_book import OrderBook


class OrderBookConverter(Protocol):
    """Protocol for converting market data events to OrderBook snapshots.

    Purpose:
        Provide a minimal, pluggable interface the engine uses to turn market data
        events (e.g., `BarEvent`, `QuoteTickEvent`, `TradeTickEvent`) into OrderBook
        snapshots that brokers can process for order matching.

    Notes:
        - Implementations dispatch by concrete $event type and return canonical
          (thin/zero-spread) OrderBooks that represent the event.
        - Prices may be negative when the market supports them; do not filter or
          reject negative values.
        - Bar events typically produce 4 OrderBooks (OHLC decomposition).
        - Trade/quote ticks produce single OrderBooks.

    Example:
        if converter.can_convert(event):
            books = converter.convert_to_order_books(event)
            for book in books:
                broker.process_order_book(book)
    """

    def can_convert(self, event: Event) -> bool:
        """Check if event can be converted to OrderBooks.

        Args:
            event: Event to check for convertibility.

        Returns:
            bool: True if event can be converted, False otherwise.
        """
        ...

    def convert_to_order_books(self, event: Event) -> list[OrderBook]:
        """Convert event to one or more OrderBook snapshots.

        Args:
            event: Event to convert.

        Returns:
            list[OrderBook]: OrderBook snapshots representing the event.
                Empty list if event cannot be converted.
        """
        ...
