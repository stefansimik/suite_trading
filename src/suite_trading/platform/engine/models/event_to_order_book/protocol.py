from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.event import Event
    from suite_trading.domain.market_data.order_book import OrderBook


class EventToOrderBookConverter(Protocol):
    """Protocol for converting market‑data events to OrderBook snapshot(s).

    Purpose:
        Provide a minimal, pluggable interface the TradingEngine uses to turn market‑data
        events (for example, `BarEvent`, `QuoteTickEvent`, `TradeTickEvent`) into
        OrderBook snapshot(s) that brokers can process for order matching.

    Notes:
        - Implementations dispatch by concrete $event type and return thin, zero‑spread
          OrderBook snapshot(s) representing the event that brokers can use for matching
          and margin calculations.
        - Prices may be negative when the market supports them; do not filter or reject
          negative values.
        - Bar events typically produce 4 OrderBooks (OHLC decomposition).
        - Trade/quote ticks produce single OrderBooks.
    """

    def can_convert(self, event: Event) -> bool:
        """Check if $event can be converted to OrderBook snapshot(s).

        Args:
            event: Event to check for convertibility.

        Returns:
            True if event can be converted, False otherwise.
        """
        ...

    def convert_to_order_books(self, event: Event) -> list[OrderBook]:
        """Convert $event to one or more OrderBook snapshot(s).

        Args:
            event: Event to convert.

        Returns:
            OrderBook snapshot(s) representing the event; empty list if unsupported.
        """
        ...
