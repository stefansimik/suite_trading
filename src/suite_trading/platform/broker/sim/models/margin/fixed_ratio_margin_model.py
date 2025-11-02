from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.monetary.money import Money
from suite_trading.utils.notional import compute_notional_value
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.platform.broker.last_price_sample_source import LastPriceSampleSource


class FixedRatioMarginModel:
    """Simple fixed-ratio margin model (symmetric long/short)."""

    # region Init

    def __init__(
        self,
        initial_ratio: Decimal,
        maintenance_ratio: Decimal,
        last_price_sample_source: LastPriceSampleSource,
    ) -> None:
        """Create a fixed-ratio margin model.

        Args:
            initial_ratio: Fraction in [0, 1] applied to notional value to compute initial margin.
            maintenance_ratio: Fraction in [0, 1] applied to notional value to compute maintenance margin.
            last_price_sample_source: Source of latest `PriceSample` for `$instrument`.

        Raises:
            ValueError: If $initial_ratio or $maintenance_ratio is outside [0, 1].
        """
        # Check: ratios in [0, 1]
        if not (Decimal("0") <= initial_ratio <= Decimal("1")):
            raise ValueError(f"Cannot call `__init__` because $initial_ratio ({initial_ratio}) is out of [0, 1]")
        if not (Decimal("0") <= maintenance_ratio <= Decimal("1")):
            raise ValueError(f"Cannot call `__init__` because $maintenance_ratio ({maintenance_ratio}) is out of [0, 1]")

        self._initial_ratio = initial_ratio
        self._maintenance_ratio = maintenance_ratio
        self._last_price_sample_source = last_price_sample_source

    # endregion

    # region Protocol MarginModel

    def compute_initial_margin(
        self,
        instrument: Instrument,
        trade_quantity: Decimal,
        is_buy: bool,
        timestamp: datetime,
    ) -> Money:
        # This model is symmetric; $is_buy is ignored by design
        sample = self._last_price_sample_source.get_last_price_sample(instrument)
        # Check: last price-sample must be available
        if sample is None:
            raise ValueError(f"Cannot call `compute_initial_margin` because $price is None for $instrument ({instrument})")

        notional_value = compute_notional_value(sample.price, trade_quantity, instrument.contract_size)
        margin_value = notional_value * self._initial_ratio
        currency = instrument.settlement_currency
        result = Money(margin_value, currency)
        return result

    def compute_maintenance_margin(
        self,
        instrument: Instrument,
        net_position_quantity: Decimal,
        timestamp: datetime,
    ) -> Money:
        sample = self._last_price_sample_source.get_last_price_sample(instrument)
        # Check: last price-sample must be available
        if sample is None:
            raise ValueError(f"Cannot call `compute_maintenance_margin` because $price is None for $instrument ({instrument})")

        notional_value = compute_notional_value(sample.price, net_position_quantity, instrument.contract_size)
        margin_value = notional_value * self._maintenance_ratio
        currency = instrument.settlement_currency
        result = Money(margin_value, currency)
        return result

    # endregion
