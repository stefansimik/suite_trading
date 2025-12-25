from __future__ import annotations

from decimal import Decimal

from datetime import datetime, timezone


from suite_trading.domain.instrument import Instrument, AssetClass
from suite_trading.domain.monetary.currency import Currency, CurrencyType
from suite_trading.domain.market_data.order_book.order_book import OrderBook, BookLevel


class TestOrderBookSimulateFills:
    """simulate_fills takes best prices first; tests are small and focused."""

    def _instrument(self) -> Instrument:
        usd = Currency("USD", 2, "US Dollar", CurrencyType.FIAT)
        return Instrument(
            name="TEST",
            exchange="XTST",
            asset_class=AssetClass.FUTURE,
            price_increment=Decimal("0.01"),
            quantity_increment=Decimal("1"),
            contract_size=Decimal("1"),
            contract_unit="contract",
            quote_currency=usd,
            settlement_currency=usd,
        )

    def _ts(self) -> datetime:
        return datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_buy_consumes_asks_best_first(self):
        """BUY should consume ask levels best-first until abs_quantity is met (10@100 then 2@101)."""
        instr = self._instrument()
        ts = self._ts()
        asks = [BookLevel(Decimal("100"), Decimal("10")), BookLevel(Decimal("101"), Decimal("5"))]
        book = OrderBook(instr, ts, bids=(), asks=tuple(asks))

        fills = book.simulate_fills(target_signed_quantity=Decimal("12"))
        pairs = [(f.signed_quantity, f.price) for f in fills]
        assert pairs == [(Decimal("10"), Decimal("100")), (Decimal("2"), Decimal("101"))]
        assert all(f.timestamp == ts for f in fills)

    def test_sell_consumes_bids_best_first(self):
        """SELL should consume bid levels best-first (4@99 then 1@98 to reach abs_quantity=5)."""
        instr = self._instrument()
        ts = self._ts()
        bids = [BookLevel(Decimal("99"), Decimal("4")), BookLevel(Decimal("98"), Decimal("7"))]
        book = OrderBook(instr, ts, bids=tuple(bids), asks=())

        fills = book.simulate_fills(target_signed_quantity=-Decimal("5"))
        pairs = [(f.signed_quantity, f.price) for f in fills]
        assert pairs == [(Decimal("-4"), Decimal("99")), (Decimal("-1"), Decimal("98"))]
        assert all(f.timestamp == ts for f in fills)

    def test_price_filters_min_max_respected(self):
        """Max price filter should cap BUY fills at 101, skipping higher levels."""
        instr = self._instrument()
        ts = self._ts()
        asks = [BookLevel(Decimal("100"), Decimal("10")), BookLevel(Decimal("101"), Decimal("10")), BookLevel(Decimal("102"), Decimal("10"))]
        book = OrderBook(instr, ts, bids=(), asks=tuple(asks))

        fills = book.simulate_fills(target_signed_quantity=Decimal("30"), max_price=Decimal("101"))
        pairs = [(f.signed_quantity, f.price) for f in fills]
        assert pairs == [(Decimal("10"), Decimal("100")), (Decimal("10"), Decimal("101"))]

    def test_negative_prices_allowed(self):
        """Support markets that allow negative prices: BUY 1 at −5 should be accepted."""
        instr = self._instrument()
        ts = self._ts()
        asks = [BookLevel(Decimal("-5"), Decimal("1"))]
        book = OrderBook(instr, ts, bids=(), asks=tuple(asks))

        fills = book.simulate_fills(target_signed_quantity=Decimal("1"))
        assert [(f.signed_quantity, f.price) for f in fills] == [(Decimal("1"), Decimal("-5"))]
