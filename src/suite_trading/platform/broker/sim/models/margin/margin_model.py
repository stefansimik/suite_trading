from __future__ import annotations

from typing import Protocol
from datetime import datetime
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.monetary.money import Money


class MarginModel(Protocol):
    """Interface for calculation of initial and maintenance margin requirements.

    The API is intentionally asymmetric:
    - Initial margin uses trade context (`$trade_quantity`, `$is_buy`) because pre-trade
      checks may depend on order direction and size.
    - Maintenance margin uses position context (`$net_position_quantity`) because ongoing
      requirements are based on current exposure, not a prospective order.
    """

    def compute_initial_margin(
        self,
        instrument: Instrument,
        price: Decimal,
        trade_quantity: Decimal,
        is_buy: bool,
        timestamp: datetime,
    ) -> Money:
        """Compute initial margin required for a prospective trade.

        Args:
            instrument: Instrument to trade.
            price: Expected trade price used for notional math.
            trade_quantity: Order size for this trade (sign may be ignored by some models).
            is_buy: True for buy orders; enables asymmetric long/short treatment.
            timestamp: Time used for schedule/venue rules.
        """
        ...

    def compute_maintenance_margin(
        self,
        instrument: Instrument,
        price: Decimal,
        net_position_quantity: Decimal,
        timestamp: datetime,
    ) -> Money:
        """Compute maintenance margin for the current net position.

        Args:
            instrument: Instrument whose position is margined.
            price: Mark price used for notional math.
            net_position_quantity: Current net position (long > 0, short < 0).
            timestamp: Time used for schedule/venue rules.
        """
        ...
