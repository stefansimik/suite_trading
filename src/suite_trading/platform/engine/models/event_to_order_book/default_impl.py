from __future__ import annotations

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar_event import BarEvent
from suite_trading.domain.market_data.tick.trade_tick_event import TradeTickEvent
from suite_trading.domain.market_data.tick.quote_tick_event import QuoteTickEvent
from suite_trading.domain.market_data.order_book.order_book import OrderBook
from suite_trading.platform.engine.models.event_to_order_book.conversion_functions import (
    bar_to_order_books,
    trade_tick_to_order_book,
    quote_tick_to_order_book,
)
from suite_trading.platform.engine.models.event_to_order_book.protocol import EventToOrderBookConverter


class DefaultEventToOrderBookConverter(EventToOrderBookConverter):
    """Default implementation of `EventToOrderBookConverter`.

    Converts market‑data events to OrderBook snapshot(s):
    - BarEvent → 4 OrderBooks (OHLC)
    - TradeTickEvent → 1 zero‑spread OrderBook
    - QuoteTickEvent → 1 level‑1 OrderBook
    """

    def can_convert(self, event: Event) -> bool:
        """Check if $event can be converted to OrderBook snapshot(s).

        Args:
            event: Event to check.

        Returns:
            True if $event is BarEvent, TradeTickEvent or QuoteTickEvent.
        """
        return isinstance(event, (BarEvent, TradeTickEvent, QuoteTickEvent))

    def convert_to_order_books(self, event: Event) -> list[OrderBook]:
        """Convert $event to OrderBook snapshot(s).

        Args:
            event: Event to convert.

        Returns:
            OrderBook snapshot(s) representing the event; empty list if unsupported.
        """
        if isinstance(event, BarEvent):
            return bar_to_order_books(event.bar)
        elif isinstance(event, TradeTickEvent):
            return [trade_tick_to_order_book(event.trade_tick)]
        elif isinstance(event, QuoteTickEvent):
            return [quote_tick_to_order_book(event.quote_tick)]
        else:
            return []
