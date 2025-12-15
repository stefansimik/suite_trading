from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.market_data.order_book.order_book import OrderBook


@runtime_checkable
class SimulatedBroker(Protocol):
    """Brokers that consume OrderBook snapshots for simulated fills.

    Used to distinguish simulated/paper/backtest brokers that need detailed
    OrderBook updates to drive simulated order-price matching and fills. Live
    brokers typically ignore these updates.
    """

    def set_current_dt(self, dt: datetime) -> None:
        """Set the broker's current simulated time.

        The `TradingEngine` injects simulated time into these brokers so time-based
        decisions (for example time-in-force expiry) can be deterministic and
        independent of wall-clock time.

        Args:
            dt: Engine time for the current event being processed.
        """
        ...

    def process_order_book(self, order_book: OrderBook) -> None:
        """Consume an OrderBook snapshot to perform simulated order-price matching and fills.

        Args:
            order_book: OrderBook snapshot to process.
        """
        ...
