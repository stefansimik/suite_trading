from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.tick.trade_tick import TradeTick
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick
from suite_trading.domain.market_data.order_book import OrderBook, BookLevel


def bar_to_order_books(bar: Bar) -> list[OrderBook]:
    """Convert Bar to 4 OrderBooks representing OHLC prices.

    Timestamps are evenly distributed across the bar interval for more
    realistic intra-bar behavior in backtesting.

    Distribution:
    - Open: start_dt
    - High: start_dt + 1/3 * duration
    - Low: start_dt + 2/3 * duration
    - Close: end_dt

    Each book has zero spread (bid=ask) at the respective OHLC price.

    Args:
        bar: Bar to convert to OrderBooks.

    Returns:
        list[OrderBook]: Four zero-spread OrderBooks at OHLC prices.
    """
    duration = bar.end_dt - bar.start_dt

    # Timestamp distribution
    t_open = bar.start_dt
    t_high = bar.start_dt + duration / 3
    t_low = bar.start_dt + 2 * duration / 3
    t_close = bar.end_dt

    # Helper to create zero-spread book
    def make_book(price: Decimal, timestamp: datetime) -> OrderBook:
        volume = bar.volume if bar.volume is not None else Decimal("0")
        level = BookLevel(price=price, volume=volume)
        return OrderBook(instrument=bar.instrument, timestamp=timestamp, bids=[level], asks=[level])

    return [
        make_book(bar.open, t_open),
        make_book(bar.high, t_high),
        make_book(bar.low, t_low),
        make_book(bar.close, t_close),
    ]


def trade_tick_to_order_book(tick: TradeTick) -> OrderBook:
    """Convert TradeTick to zero-spread OrderBook.

    Both bid and ask are set to trade price with trade volume.
    This models guaranteed fill at the trade price for both sides.

    Args:
        tick: TradeTick to convert.

    Returns:
        OrderBook: Zero-spread OrderBook at trade price.
    """
    level = BookLevel(price=tick.price, volume=tick.volume)
    return OrderBook(instrument=tick.instrument, timestamp=tick.timestamp, bids=[level], asks=[level])


def quote_tick_to_order_book(tick: QuoteTick) -> OrderBook:
    """Convert QuoteTick to 1-level OrderBook.

    Direct mapping: bid → first bid level, ask → first ask level.

    Args:
        tick: QuoteTick to convert.

    Returns:
        OrderBook: 1-level OrderBook with bid and ask.
    """
    bid_level = BookLevel(price=tick.bid_price, volume=tick.bid_volume)
    ask_level = BookLevel(price=tick.ask_price, volume=tick.ask_volume)
    return OrderBook(instrument=tick.instrument, timestamp=tick.timestamp, bids=[bid_level], asks=[ask_level])
