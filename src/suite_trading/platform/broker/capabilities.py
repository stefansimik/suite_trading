from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.market_data.price_sample import PriceSample


@runtime_checkable
class PriceSampleProcessor(Protocol):
    """Capability marker for component that can process price samples.

     Common example is `SimBroker`, that consumes PriceSample's to drive order/price matching.

    Args:
        sample (PriceSample): Latest price sample for an instrument.
    """

    def process_price_sample(self, sample: PriceSample) -> None:
        """Consume and process $sample"""
        ...
