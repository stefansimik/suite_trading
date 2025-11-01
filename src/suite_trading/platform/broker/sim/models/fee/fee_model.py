from __future__ import annotations

from typing import Iterable, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.order.execution import Execution
    from suite_trading.domain.monetary.money import Money


# region Interface


class FeeModel(Protocol):
    """Domain interface for fee modeling used by the simulated broker.

    You get two inputs: the $execution being priced now and all $previous_executions recorded
    earlier in the session. We pass previous executions so models can look at cumulative activity
    (e.g., volume tiers, monthly minimums, free-trade quotas).

    Args:
        execution: The execution currently being priced for commission.
        previous_executions: All executions recorded before $execution. The current execution is
            NOT included.

    Returns:
        Commission as Money in the appropriate currency.
    """

    def compute_commission(
        self,
        execution: Execution,
        previous_executions: Iterable[Execution],
    ) -> Money: ...


# endregion
