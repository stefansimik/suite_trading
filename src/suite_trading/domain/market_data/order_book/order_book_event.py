from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Callable

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.order_book.order_book import OrderBook
from suite_trading.utils.datetime_tools import format_dt


class OrderBookEvent(Event):
    """Event wrapper carrying order book data with system metadata.

    This event represents the arrival of a new order book snapshot in the trading system.
    It contains both the pure order book data and event processing metadata.

    Attributes:
        order_book: The pure order book data object containing bid and ask levels.
        dt_received: When the event entered our system (timezone-aware UTC).
        is_historical: Whether this order book snapshot is historical or live.
    """

    __slots__ = ("_order_book", "_is_historical")

    # region Init

    def __init__(
        self,
        order_book: OrderBook,
        dt_received: datetime,
        is_historical: bool,
    ) -> None:
        """Initialize a new order book event.

        Args:
            order_book: The pure order book snapshot.
            dt_received: When the event entered our system (timezone-aware UTC).
            is_historical: Whether this order book snapshot is historical or live.
        """
        super().__init__(dt_event=order_book.timestamp, dt_received=dt_received)
        self._order_book = order_book
        self._is_historical = is_historical

    # endregion

    # region Properties

    @property
    def order_book(self) -> OrderBook:
        """Get the order book snapshot."""
        return self._order_book

    @property
    def dt_received(self) -> datetime:
        """Get the received timestamp."""
        return self._dt_received

    @property
    def is_historical(self) -> bool:
        """Return whether this order book snapshot is historical or live."""
        return self._is_historical

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the order book snapshot was recorded.

        For order book events, this is the timestamp of the underlying snapshot.

        Returns:
            Datetime when the snapshot was recorded.
        """
        return self.order_book.timestamp

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(order_book={self.order_book}, dt_received={format_dt(self.dt_received)}, is_historical={self.is_historical})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(order_book={self.order_book!r}, dt_received={format_dt(self.dt_received)}, is_historical={self.is_historical})"

    def __eq__(self, other) -> bool:
        """Check equality with another order book event.

        Args:
            other: The other object to compare with.

        Returns:
            True if order book events are equal, False otherwise.
        """
        if not isinstance(other, OrderBookEvent):
            return False
        return self.order_book == other.order_book and self.dt_received == other.dt_received and self.is_historical == other.is_historical

    # endregion


# region Utilities


def wrap_order_books_to_events(
    order_books: Iterable[OrderBook],
    *,
    is_historical: bool = True,
    dt_received_getter: Callable[[OrderBook], datetime] | None = None,
) -> Iterator[OrderBookEvent]:
    """Wrap $order_books into $OrderBookEvent(s) with predictable $dt_received defaults.

    Args:
        order_books: Iterable of $OrderBook instances to wrap.
        is_historical: Whether produced $OrderBookEvent(s) represent historical data.
        dt_received_getter: Function mapping an $OrderBook to its $dt_received timestamp.
            Defaults to order_book.timestamp for deterministic historical usage.

    Returns:
        A lazy iterator of wrapped events.
    """
    if dt_received_getter is None:
        dt_received_getter = lambda ob: ob.timestamp  # noqa: E731

    for ob in order_books:
        # Check: ensure dt_received is provided via getter per snapshot for clarity
        yield OrderBookEvent(order_book=ob, dt_received=dt_received_getter(ob), is_historical=is_historical)


# endregion
