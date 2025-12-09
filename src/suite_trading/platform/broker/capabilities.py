from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.market_data.order_book.order_book import OrderBook


@runtime_checkable
class OrderBookSimulatedBroker(Protocol):
    """Brokers that consume OrderBook snapshots for simulated fills.

    Used to distinguish simulated/paper/backtest brokers that need detailed
    OrderBook updates to drive simulated order-price matching and fills. Live
    brokers typically ignore these updates.
    """

    def process_order_book(self, order_book: OrderBook) -> None:
        """Consume an OrderBook snapshot to perform simulated order-price matching and fills.

        Args:
            order_book: OrderBook snapshot to process.
        """
        ...
