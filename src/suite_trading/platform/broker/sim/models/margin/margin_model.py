from __future__ import annotations

from typing import Protocol
from datetime import datetime
from decimal import Decimal

from suite_trading.domain.monetary.money import Money
from suite_trading.domain.market_data.order_book import OrderBook


class MarginModel(Protocol):
    """Interface for calculation of initial and maintenance margin requirements.

    The API is intentionally asymmetric:
    - Initial margin uses trade context (`$trade_quantity`, `$is_buy`) because pre-trade
      checks may depend on order direction and size.
    - Maintenance margin uses position context (`$net_position_quantity`) because ongoing
      requirements are based on current exposure, not a prospective order.

    Both methods receive the same `OrderBook` snapshot that the broker uses to match the
    trade or value the position. Callers are responsible for selecting the correct
    snapshot for their own timeline; implementations should treat the provided
    `OrderBook` as the single source of pricing truth rather than reading global broker
    state.

    The `$timestamp` argument represents the time when margin is calculated. In the simple
    simulation broker this is usually the same as `$order_book.timestamp`, but callers may
    pass a different time when they want to evaluate margin at another moment.
    """

    def compute_initial_margin(
        self,
        order_book: OrderBook,
        trade_quantity: Decimal,
        is_buy: bool,
        timestamp: datetime,
    ) -> Money:
        """Compute initial margin required for a prospective trade.

        Args:
            order_book: OrderBook snapshot that the broker uses to price and match this trade.
            trade_quantity: Order size for this trade (sign may be ignored by some models).
            is_buy: True for buy orders; enables asymmetric long/short treatment.
            timestamp: Time when margin is calculated for this trade. Usually the same as
                `$order_book.timestamp`, but callers can pass a different evaluation time.
        """
        ...

    def compute_maintenance_margin(
        self,
        order_book: OrderBook,
        net_position_quantity: Decimal,
        timestamp: datetime,
    ) -> Money:
        """Compute maintenance margin for the current net position.

        Args:
            order_book: OrderBook snapshot that the broker uses to value this position.
            net_position_quantity: Current net position (long > 0, short < 0).
            timestamp: Time when margin is calculated for this position. Usually the same as
                `$order_book.timestamp`, but callers can pass a different evaluation time.
        """
        ...
