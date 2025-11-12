from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.monetary.money import Money
from suite_trading.utils.notional import compute_notional_value
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.platform.broker.last_order_book_source import LastOrderBookSource


class FixedRatioMarginModel:
    """Simple fixed-ratio margin model (symmetric long/short)."""

    # region Init

    def __init__(
        self,
        initial_ratio: Decimal,
        maintenance_ratio: Decimal,
        last_order_book_source: LastOrderBookSource,
    ) -> None:
        """Create a fixed-ratio margin model.

        Args:
            initial_ratio: Fraction in [0, 1] applied to notional value to compute initial margin.
            maintenance_ratio: Fraction in [0, 1] applied to notional value to compute maintenance margin.
            last_order_book_source: Source of latest OrderBook for $instrument.

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
        self._last_order_book_source = last_order_book_source

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
        book = self._last_order_book_source.get_last_order_book(instrument)
        # Check: last order book must be available
        if book is None:
            raise ValueError(f"Cannot call `compute_initial_margin` because OrderBook is None for $instrument ({instrument})")

        price = self._extract_price_from_order_book(book, instrument)
        notional_value = compute_notional_value(price, trade_quantity, instrument.contract_size)
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
        book = self._last_order_book_source.get_last_order_book(instrument)
        # Check: last order book must be available
        if book is None:
            raise ValueError(f"Cannot call `compute_maintenance_margin` because OrderBook is None for $instrument ({instrument})")

        price = self._extract_price_from_order_book(book, instrument)
        notional_value = compute_notional_value(price, net_position_quantity, instrument.contract_size)
        margin_value = notional_value * self._maintenance_ratio
        currency = instrument.settlement_currency
        result = Money(margin_value, currency)
        return result

    # endregion

    # region Utilities

    def _extract_price_from_order_book(self, book, instrument: Instrument) -> Decimal:
        """Extract a representative price from OrderBook for margin calculations.

        Uses execution price for zero-spread books, otherwise uses mid price.

        Args:
            book: OrderBook to extract price from.
            instrument: Instrument for error messages.

        Returns:
            Decimal: Representative price.

        Raises:
            ValueError: If OrderBook is empty on both sides.
        """
        best_bid = book.best_bid
        best_ask = book.best_ask

        # Zero-spread book (trade or bar): use execution price
        if best_bid and best_ask and best_bid.price == best_ask.price:
            return best_bid.price

        # Quote book: use MID
        if best_bid and best_ask:
            return (best_bid.price + best_ask.price) / Decimal("2")

        # One-sided book: use available side
        if best_ask:
            return best_ask.price
        if best_bid:
            return best_bid.price

        raise ValueError(f"Cannot call `_extract_price_from_order_book` because OrderBook is empty on both sides for $instrument ({instrument})")

    # endregion
