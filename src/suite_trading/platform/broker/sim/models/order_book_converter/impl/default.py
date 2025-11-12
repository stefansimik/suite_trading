from __future__ import annotations

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar_event import BarEvent
from suite_trading.domain.market_data.tick.trade_tick_event import TradeTickEvent
from suite_trading.domain.market_data.tick.quote_tick_event import QuoteTickEvent
from suite_trading.domain.market_data.order_book import OrderBook
from suite_trading.platform.broker.sim.models.order_book_converter.conversion_functions import (
    bar_to_order_books,
    trade_tick_to_order_book,
    quote_tick_to_order_book,
)


class DefaultOrderBookConverter:
    """Default implementation of OrderBookConverter protocol.

    Converts market data events to OrderBook snapshots:
    - BarEvent → 4 OrderBooks (OHLC)
    - TradeTickEvent → 1 zero-spread OrderBook
    - QuoteTickEvent → 1 level-1 OrderBook
    """

    def can_convert(self, event: Event) -> bool:
        """Check if event can be converted to OrderBooks.

        Args:
            event: Event to check.

        Returns:
            bool: True if event is BarEvent, TradeTickEvent, or QuoteTickEvent.
        """
        return isinstance(event, (BarEvent, TradeTickEvent, QuoteTickEvent))

    def convert_to_order_books(self, event: Event) -> list[OrderBook]:
        """Convert event to OrderBook snapshots.

        Args:
            event: Event to convert.

        Returns:
            list[OrderBook]: OrderBooks representing the event.
                Empty list if event type is not supported.
        """
        if isinstance(event, BarEvent):
            return bar_to_order_books(event.bar)
        elif isinstance(event, TradeTickEvent):
            return [trade_tick_to_order_book(event.trade_tick)]
        elif isinstance(event, QuoteTickEvent):
            return [quote_tick_to_order_book(event.quote_tick)]
        else:
            return []
