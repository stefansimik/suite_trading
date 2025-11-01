from __future__ import annotations

from typing import Iterable, TYPE_CHECKING

from .fee_model import FeeModel

if TYPE_CHECKING:
    from suite_trading.domain.monetary.money import Money
    from suite_trading.domain.order.execution import Execution


class FixedFeeModel(FeeModel):
    """Fixed per-unit commission model.

    Args:
        fee_per_unit: Commission `Money` charged for each 1 unit executed.
            Example: 0.005 USD per share → Money(Decimal("0.005"), USD)
    """

    __slots__ = ("_fee_per_unit",)

    def __init__(self, fee_per_unit: Money) -> None:
        self._fee_per_unit = fee_per_unit

    def compute_commission(
        self,
        execution: Execution,
        previous_executions: Iterable[Execution],
    ) -> Money:
        result = self._fee_per_unit * execution.quantity
        return result
