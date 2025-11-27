from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal as D

from suite_trading.domain.instrument import Instrument, AssetClass
from suite_trading.domain.monetary.currency import Currency, CurrencyType
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick
from suite_trading.domain.market_data.tick.quote_tick_event import QuoteTickEvent
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed


class _SubmitAndRecordStrategy(Strategy):
    """Adds a one-tick quotes feed and submits a Market BUY in the callback; records executions."""

    def __init__(self, name: str, broker: SimBroker, instrument: Instrument, bid: D, ask: D, ts: datetime) -> None:
        super().__init__(name)
        self._broker = broker
        self._instrument = instrument
        self._bid = bid
        self._ask = ask
        self._ts = ts
        self._submitted = False
        self.executions = []

    def on_start(self) -> None:
        tick = QuoteTick(self._instrument, self._bid, self._ask, D("10"), D("10"), self._ts)
        self.add_event_feed("q", FixedSequenceEventFeed([QuoteTickEvent(tick, self._ts)]))

    def on_event(self, event) -> None:
        if not self._submitted:
            # Submit via Strategy API so TradingEngine coordinates routing
            from suite_trading.domain.order.orders import MarketOrder

            self.submit_order(MarketOrder(self._instrument, OrderSide.BUY, D("1")), self._broker)
            self._submitted = True

    def on_execution(self, execution) -> None:
        self.executions.append(execution)
        self.remove_event_feed("q")


class TestEngineOrderRoutingMarket:
    def _instrument(self) -> Instrument:
        usd = Currency("USD", 2, "US Dollar", CurrencyType.FIAT)
        return Instrument(name="TEST", exchange="XTST", asset_class=AssetClass.FUTURE, price_increment=D("0.01"), quantity_increment=D("1"), contract_size=D("1"), contract_unit="contract", quote_currency=usd, settlement_currency=usd)

    def _ts(self) -> datetime:
        return datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_engine_routes_execution_back_to_originating_strategy(self):
        """Engine should route execution callback to the same Strategy that submitted the order."""
        instr = self._instrument()
        broker = SimBroker()
        engine = TradingEngine()
        strategy = _SubmitAndRecordStrategy("s1", broker, instr, D("99"), D("101"), self._ts())

        engine.add_broker("sim", broker)
        engine.add_strategy(strategy)

        engine.start()

        assert len(strategy.executions) == 1
        # Price should be the ask from the quote tick
        assert strategy.executions[0].price == D("101")

    def test_deterministic_callbacks_for_two_orders_same_time(self):
        """Two strategies submit at the same time; each must receive exactly one execution for its own order."""
        instr = self._instrument()
        broker = SimBroker()
        engine = TradingEngine()
        s1 = _SubmitAndRecordStrategy("s1", broker, instr, D("99"), D("101"), self._ts())
        s2 = _SubmitAndRecordStrategy("s2", broker, instr, D("99"), D("101"), self._ts())

        engine.add_broker("sim", broker)
        engine.add_strategy(s1)
        engine.add_strategy(s2)

        engine.start()

        # Both should receive exactly one execution routed back to the correct Strategy
        assert len(s1.executions) == 1 and s1.executions[0].order.is_buy
        assert len(s2.executions) == 1 and s2.executions[0].order.is_buy
