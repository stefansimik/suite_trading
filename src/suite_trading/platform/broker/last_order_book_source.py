from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.instrument import Instrument
    from suite_trading.domain.market_data.order_book import OrderBook


class LastOrderBookSource(Protocol):
    """Protocol for components that can provide last known OrderBook per instrument."""

    def get_last_order_book(self, instrument: Instrument) -> OrderBook | None:
        """Return latest known OrderBook for $instrument, or None if unknown.

        Args:
            instrument: Instrument to get OrderBook for.

        Returns:
            OrderBook | None: Latest OrderBook snapshot, or None if not available.
        """
