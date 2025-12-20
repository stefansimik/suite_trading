from __future__ import annotations

from typing import Iterable, Protocol, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal

if TYPE_CHECKING:
    from suite_trading.domain.order.orders import Order
    from suite_trading.domain.order.order_fill import OrderFill
    from suite_trading.domain.monetary.money import Money


# region Interface


class FeeModel(Protocol):
    """Domain interface for fee modeling used by the simulated broker.

    The fee is computed from primitive inputs so that `OrderFill` can be constructed with an
    already-known $commission. We also pass $previous_order_fills so models can consider cumulative
    activity (e.g., volume tiers, minimum tickets).

    Args:
        order: The Order associated with this order_fill.
        price: Snapped order_fill price used as fee basis.
        absolute_quantity: Snapped order_fill absolute quantity used as fee basis.
        timestamp: Time of the order_fill.
        previous_order_fills: All order fills recorded before this one for context; current
            $order_fill is NOT included.

    Returns:
        Commission as Money in the appropriate currency.
    """

    def compute_commission(
        self,
        order: Order,
        price: Decimal,
        absolute_quantity: Decimal,
        timestamp: datetime,
        previous_order_fills: Iterable[OrderFill],
    ) -> Money: ...


# endregion
