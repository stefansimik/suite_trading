from __future__ import annotations

from typing import Iterable, Protocol, TYPE_CHECKING
from datetime import datetime
from decimal import Decimal

if TYPE_CHECKING:
    from suite_trading.domain.order.orders import Order
    from suite_trading.domain.order.execution import Execution
    from suite_trading.domain.monetary.money import Money


# region Interface


class FeeModel(Protocol):
    """Domain interface for fee modeling used by the simulated broker.

    The fee is computed from primitive inputs so that `Execution` can be constructed with an
    already-known $commission. We also pass $previous_executions so models can consider cumulative
    activity (e.g., volume tiers, minimum tickets).

    Args:
        order: The Order associated with this execution.
        price: Snapped execution price used as fee basis.
        quantity: Snapped execution quantity used as fee basis.
        timestamp: Time of the execution.
        previous_executions: All executions recorded before this one for context; current
            execution is NOT included.

    Returns:
        Commission as Money in the appropriate currency.
    """

    def compute_commission(
        self,
        order: Order,
        price: Decimal,
        quantity: Decimal,
        timestamp: datetime,
        previous_executions: Iterable[Execution],
    ) -> Money: ...


# endregion
