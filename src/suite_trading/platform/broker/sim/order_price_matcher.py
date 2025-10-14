from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.domain.order.execution import Execution
from suite_trading.domain.order.orders import Order


@dataclass(frozen=True)
class MatchResult:
    """Result of matching a single `PriceSample` against orders.

    Attributes:
      executions: Proposed `Execution`(s) for the provided orders.
      updated_orders: Latest Order objects whose state should be applied by the broker.
    """

    executions: list[Execution]
    updated_orders: list[Order]


class OrderPriceMatcher:
    """Order–price matching facade used by SimBroker.

    Policy:
    - `SimBroker` supplies active orders for the instrument and consumes results.

    TODO: Implement real matching logic (market/limit/stop/stop-limit, TIF, partials).
    """

    def match_sample(
        self,
        sample: PriceSample,
        orders: Iterable[Order],
    ) -> MatchResult:
        """Evaluate $sample against $orders and propose effects.

        Args:
          sample: Single `PriceSample` to evaluate.
          orders: Active `Order`(s) targeting `sample.instrument`.

        Returns:
          MatchResult: Proposed executions and order-state transitions.

        TODO: Implement real logic
            Fill behavior comes from `FillModel`.
            Account-level checks (fees, margin, leverage) are handled by `SimBroker` using
            `FeeModel`, `MarginModel`, and `LeverageModel` before/after matching. The matcher
            assumes quantities are risk-approved and may accept a per-order quantity cap if
            needed.
        """
        return MatchResult(executions=[], updated_orders=[])
