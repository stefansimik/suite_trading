from __future__ import annotations

from typing import NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.strategy.strategy import Strategy
    from suite_trading.platform.broker.broker import Broker


class StrategyBrokerPair(NamedTuple):
    """Pairs a Strategy with a Broker for order routing.

    This tiny value object captures the routing path for an Order:
    - $strategy is the origin that submitted the order and receives callbacks
    - $broker executes the order and reports updates

    Keep this simple (KISS) and domain-focused (routing), not a generic "pair".

    Attributes:
        strategy: Strategy that owns the order and receives callbacks.
        broker: Broker that executes the order.
    """

    strategy: Strategy
    broker: Broker
