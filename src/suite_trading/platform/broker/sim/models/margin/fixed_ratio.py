from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from suite_trading.utils.decimal_tools import DecimalLike, as_decimal

from suite_trading.domain.market_data.order_book.order_book import OrderBook
from suite_trading.domain.monetary.money import Money
from suite_trading.utils.notional import compute_notional_value

from .protocol import MarginModel


class FixedRatioMarginModel(MarginModel):
    """Simple fixed-ratio margin model (symmetric long/short)."""

    # region Init

    def __init__(
        self,
        initial_ratio: DecimalLike,
        maintenance_ratio: DecimalLike,
    ) -> None:
        """Create a fixed-ratio margin model.

        Args:
            initial_ratio: Fraction in [0, 1] applied to notional value to compute initial margin.
                Accepts Decimal-like scalar.
            maintenance_ratio: Fraction in [0, 1] applied to notional value to compute maintenance margin.
                Accepts Decimal-like scalar.

        Raises:
            ValueError: If $initial_ratio or $maintenance_ratio is outside [0, 1].
        """
        initial_ratio_decimal = as_decimal(initial_ratio)
        maintenance_ratio_decimal = as_decimal(maintenance_ratio)

        # Precondition: ratios in [0, 1]
        if not (Decimal("0") <= initial_ratio_decimal <= Decimal("1")):
            raise ValueError(f"Cannot call `__init__` because $initial_ratio ({initial_ratio_decimal}) is out of [0, 1]")
        if not (Decimal("0") <= maintenance_ratio_decimal <= Decimal("1")):
            raise ValueError(f"Cannot call `__init__` because $maintenance_ratio ({maintenance_ratio_decimal}) is out of [0, 1]")

        self._initial_ratio = initial_ratio_decimal
        self._maintenance_ratio = maintenance_ratio_decimal

    # endregion

    # region Protocol MarginModel

    def compute_initial_margin(
        self,
        order_book: OrderBook,
        signed_quantity: DecimalLike,
        timestamp: datetime,
    ) -> Money:
        # This model is symmetric; $timestamp is ignored by design
        q = as_decimal(signed_quantity)
        instrument = order_book.instrument
        price = self._extract_price_from_order_book(order_book)
        notional_value = compute_notional_value(price, q, instrument.contract_size)
        margin_value = notional_value * self._initial_ratio
        currency = instrument.settlement_currency
        result = Money(margin_value, currency)
        return result

    def compute_maintenance_margin(
        self,
        order_book: OrderBook,
        signed_quantity: DecimalLike,
        timestamp: datetime,
    ) -> Money:
        q = as_decimal(signed_quantity)
        instrument = order_book.instrument
        price = self._extract_price_from_order_book(order_book)
        notional_value = compute_notional_value(price, q, instrument.contract_size)
        margin_value = notional_value * self._maintenance_ratio
        currency = instrument.settlement_currency
        result = Money(margin_value, currency)
        return result

    # endregion

    # region Utilities

    def _extract_price_from_order_book(self, order_book: OrderBook) -> Decimal:
        """Extract a representative price from OrderBook for margin calculations.

        Uses order_fill price for zero-spread books, otherwise uses mid price.

        Args:
            order_book: OrderBook to extract price from.

        Returns:
            Decimal: Representative price.

        Raises:
            ValueError: If OrderBook is empty on both sides.
        """
        best_bid = order_book.best_bid
        best_ask = order_book.best_ask

        return (best_bid.price + best_ask.price) / Decimal("2")

    # endregion
