from __future__ import annotations

from typing import Protocol
from datetime import datetime
from decimal import Decimal

from suite_trading.domain.monetary.money import Money
from suite_trading.domain.market_data.order_book.order_book import OrderBook


class MarginModel(Protocol):
    """Interface for calculation of initial and maintenance margin requirements.

    The API is intentionally asymmetric:

    - Initial margin uses trade context ($trade_quantity, $is_buy) because pre-trade
      checks may depend on order direction and size.
    - Maintenance margin uses position context ($net_position_quantity) because ongoing
      requirements are based on current exposure, not a prospective order.

    Both methods receive the same OrderBook snapshot that the broker uses to match the
    trade or value the position. Callers are responsible for selecting the correct
    snapshot for their own timeline; implementations should treat the provided
    $order_book as the single source of pricing truth rather than reading global broker
    state.

    The $timestamp argument represents the time when margin is calculated. In the simple
    simulation broker this is usually the same as $order_book.timestamp, but callers may
    pass a different time when they want to evaluate margin at another moment.

    Per-fill execution and incremental blocking:

    - Simulated brokers such as SimBroker call `compute_initial_margin` per proposed fill,
      not once for the whole order. The $trade_quantity passed in is the additional
      exposure introduced by the current proposed fill, not the total order quantity.
    - Initial margin is therefore blocked incrementally per proposed fill, only when absolute
      exposure increases. If a proposed fill reduces exposure or keeps it unchanged, the
      implementation may return a zero $Money amount and no new initial margin is
      blocked.
    - After each proposed fill is executed, the broker recomputes maintenance margin for the new
      $net_position_quantity and converts previously blocked initial margin into
      maintenance margin.

    Currency and cross-currency handling:

    - All values are represented as $Money. Implementations must return amounts in a
      currency that is compatible with the broker's Account and FeeModel configuration
      because $Money arithmetic requires matching currencies.
    - The current simulation stack assumes a single settlement currency per account;
      there is no automatic FX conversion inside the MarginModel or broker. Any
      cross-currency behavior must be modeled explicitly by the caller or a higher-level
      component.
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
                $order_book.timestamp, but callers can pass a different evaluation time.
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
                $order_book.timestamp, but callers can pass a different evaluation time.
        """
        ...
