from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.market_data.order_book import OrderBook


@runtime_checkable
class OrderBookDrivenBroker(Protocol):
    """Brokers that rely on OrderBook updates to simulate price matching.

    Used to distinguish simulated/paper/backtest brokers that need detailed price
    updates to drive order matching. Live brokers typically ignore these updates.
    """

    def process_order_book(self, order_book: OrderBook) -> None:
        """Consume an OrderBook snapshot to perform simulated order-price matching.

        Args:
            order_book: OrderBook snapshot to process.
        """
        ...
