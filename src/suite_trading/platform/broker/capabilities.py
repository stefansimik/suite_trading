from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.market_data.order_book import OrderBook


@runtime_checkable
class OrderBookProcessor(Protocol):
    """Capability marker for components that process order book snapshots.

    Common example is `SimBroker`, that consumes OrderBook snapshots to drive
    order matching and fill simulation.
    """

    def process_order_book(self, book: OrderBook) -> None:
        """Process OrderBook for order matching and fills.

        Args:
            book: OrderBook snapshot to process.
        """
        ...
