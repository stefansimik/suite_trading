from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal as D


from suite_trading.domain.instrument import Instrument, AssetClass
from suite_trading.domain.monetary.currency import Currency, CurrencyType
from suite_trading.domain.market_data.order_book import OrderBook, BookLevel
from suite_trading.domain.order.order_enums import OrderSide


class TestOrderBookSimulateFills:
    """simulate_fills takes best prices first; tests are small and focused."""

    def _instrument(self) -> Instrument:
        usd = Currency("USD", 2, "US Dollar", CurrencyType.FIAT)
        return Instrument(
            name="TEST",
            exchange="XTST",
            asset_class=AssetClass.FUTURE,
            price_increment=D("0.01"),
            quantity_increment=D("1"),
            contract_size=D("1"),
            contract_unit="contract",
            quote_currency=usd,
            settlement_currency=usd,
        )

    def _ts(self) -> datetime:
        return datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_buy_consumes_asks_best_first(self):
        """BUY should consume ask levels best-first until qty is met (10@100 then 2@101)."""
        instr = self._instrument()
        ts = self._ts()
        asks = [BookLevel(D("100"), D("10")), BookLevel(D("101"), D("5"))]
        book = OrderBook(instr, ts, bids=(), asks=tuple(asks))

        fills = book.simulate_fills(order_side=OrderSide.BUY, target_quantity=D("12"))
        pairs = [(f.quantity, f.price) for f in fills]
        assert pairs == [(D("10"), D("100")), (D("2"), D("101"))]

    def test_sell_consumes_bids_best_first(self):
        """SELL should consume bid levels best-first (4@99 then 1@98 to reach qty=5)."""
        instr = self._instrument()
        ts = self._ts()
        bids = [BookLevel(D("99"), D("4")), BookLevel(D("98"), D("7"))]
        book = OrderBook(instr, ts, bids=tuple(bids), asks=())

        fills = book.simulate_fills(order_side=OrderSide.SELL, target_quantity=D("5"))
        pairs = [(f.quantity, f.price) for f in fills]
        assert pairs == [(D("4"), D("99")), (D("1"), D("98"))]

    def test_price_filters_min_max_respected(self):
        """Max price filter should cap BUY fills at 101, skipping higher levels."""
        instr = self._instrument()
        ts = self._ts()
        asks = [BookLevel(D("100"), D("10")), BookLevel(D("101"), D("10")), BookLevel(D("102"), D("10"))]
        book = OrderBook(instr, ts, bids=(), asks=tuple(asks))

        fills = book.simulate_fills(order_side=OrderSide.BUY, target_quantity=D("30"), max_price=D("101"))
        pairs = [(f.quantity, f.price) for f in fills]
        assert pairs == [(D("10"), D("100")), (D("10"), D("101"))]

    def test_negative_prices_allowed(self):
        """Support markets that allow negative prices: BUY 1 at −5 should be accepted."""
        instr = self._instrument()
        ts = self._ts()
        asks = [BookLevel(D("-5"), D("1"))]
        book = OrderBook(instr, ts, bids=(), asks=tuple(asks))

        fills = book.simulate_fills(order_side=OrderSide.BUY, target_quantity=D("1"))
        assert [(f.quantity, f.price) for f in fills] == [(D("1"), D("-5"))]
