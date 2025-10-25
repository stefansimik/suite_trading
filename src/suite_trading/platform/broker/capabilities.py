from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.market_data.price_sample import PriceSample


@runtime_checkable
class PriceSampleConsumer(Protocol):
    """Capability marker for brokers that consume price samples to drive order/price matching.

    Implement on simulated brokers that need to turn prices into order-executions and order-state updates.

    Args:
        sample (PriceSample): Latest price sample for an instrument.
    """

    def process_price_sample(self, sample: PriceSample) -> None:
        """Consume $sample to advance broker's matching logic."""
        ...
