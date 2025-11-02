from __future__ import annotations

from typing import Protocol

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.price_sample import PriceSample


class LastPriceSampleSource(Protocol):
    """Cheap lookup of the broker's last `PriceSample` for an `Instrument`.

    Returns:
        The latest known `PriceSample` for `$instrument`, or `None` when unknown.
    """

    def get_last_price_sample(self, instrument: Instrument) -> PriceSample | None: ...
