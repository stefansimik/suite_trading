from __future__ import annotations

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
        initial_margin_ratio: DecimalLike,
        maint_margin_ratio: DecimalLike,
    ) -> None:
        """Create a fixed-ratio margin model.

        Args:
            initial_margin_ratio: Fraction in [0, 1] applied to notional value to compute initial margin.
                Accepts Decimal-like scalar.
            maint_margin_ratio: Fraction in [0, 1] applied to notional value to compute maintenance margin.
                Accepts Decimal-like scalar.

        Raises:
            ValueError: If $initial_margin_ratio or $maint_margin_ratio is outside [0, 1].
        """
        initial_margin_ratio = as_decimal(initial_margin_ratio)
        maint_margin_ratio = as_decimal(maint_margin_ratio)

        # Raise: ratios in [0, 1]
        if not (Decimal("0") <= initial_margin_ratio <= Decimal("1")):
            raise ValueError(f"Cannot call `__init__` because $initial_margin_ratio ({initial_margin_ratio}) is out of [0, 1]")
        if not (Decimal("0") <= maint_margin_ratio <= Decimal("1")):
            raise ValueError(f"Cannot call `__init__` because $maint_margin_ratio ({maint_margin_ratio}) is out of [0, 1]")

        self._initial_margin_ratio = initial_margin_ratio
        self._maint_margin_ratio = maint_margin_ratio

    # endregion

    # region Protocol MarginModel

    def compute_initial_margin(
        self,
        order_book: OrderBook,
        signed_qty: DecimalLike,
    ) -> Money:
        """Implements: MarginModel.compute_initial_margin

        Compute initial margin for a position change of $signed_qty using the current $order_book.
        """
        signed_qty = as_decimal(signed_qty)
        instrument = order_book.instrument
        price = self._extract_price_from_order_book(order_book)
        notional_value = compute_notional_value(price, signed_qty, instrument.contract_size)
        margin_value = notional_value * self._initial_margin_ratio
        currency = instrument.settlement_currency
        result = Money(margin_value, currency)
        return result

    def compute_maintenance_margin(
        self,
        order_book: OrderBook,
        signed_qty: DecimalLike,
    ) -> Money:
        """Implements: MarginModel.compute_maintenance_margin

        Compute maintenance margin for a net position of $signed_qty using the current $order_book.
        """
        signed_qty = as_decimal(signed_qty)
        instrument = order_book.instrument
        price = self._extract_price_from_order_book(order_book)
        notional_value = compute_notional_value(price, signed_qty, instrument.contract_size)
        margin_value = notional_value * self._maint_margin_ratio
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

        # Raise: OrderBook must have quotes on both sides to compute mid price
        if best_bid is None or best_ask is None:
            raise ValueError(f"Cannot call `_extract_price_from_order_book` because OrderBook for Instrument '{order_book.instrument}' is empty on one or both sides (bid={best_bid}, ask={best_ask})")

        return (best_bid.price + best_ask.price) / Decimal("2")

    # endregion
