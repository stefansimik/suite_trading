from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal as D

from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.strategy.strategy import Strategy
from suite_trading.domain.order.orders import MarketOrder
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.domain.market_data.tick.trade_tick import TradeTick
from suite_trading.domain.market_data.tick.trade_tick_event import TradeTickEvent
from suite_trading.domain.instrument import Instrument, AssetClass
from suite_trading.domain.monetary.currency_registry import USD
from suite_trading.domain.event import Event


def _instr() -> Instrument:
    return Instrument(name="TEST", exchange="XTST", asset_class=AssetClass.FUTURE, price_increment=D("0.01"), quantity_increment=D("1"), contract_size=D("1"), contract_unit="contract", quote_currency=USD)


def _create_optimistic_sim_broker() -> SimBroker:
    fill_model = DistributionFillModel(market_fill_adjustment_distribution={0: D("1")}, limit_on_touch_fill_probability=D("1"), rng_seed=42)
    return SimBroker(fill_model=fill_model)


class _KickoffEvent(Event):
    """Non-convertible event to submit while Strategy is RUNNING but before any order-book exists."""

    def __init__(self, dt: datetime) -> None:
        super().__init__(dt_event=dt, dt_received=dt)


class _TradesSubmitInCallbackStrategy(Strategy):
    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self.executions = []
        self._submitted = False

    def on_start(self) -> None:
        instr = _instr()
        t0 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        ticks = [TradeTickEvent(TradeTick(instr, D("250"), D("10"), t0), t0)]
        self.add_event_feed("trades", FixedSequenceEventFeed(ticks), use_for_simulated_fills=True)

    def on_event(self, event) -> None:
        if not self._submitted:
            instr = event.trade_tick.instrument
            self.submit_order(MarketOrder(instr, OrderSide.SELL, D("2")), self._broker)
            self._submitted = True

    def on_execution(self, execution) -> None:
        self.executions.append(execution)
        self.remove_event_feed("trades")


class _TradesSubmitBeforeTicksStrategy(Strategy):
    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self.executions = []
        self._submitted = False
        self._instr: Instrument | None = None
        self._t0: datetime | None = None

    def on_start(self) -> None:
        # Defer submission until RUNNING by using a kickoff event earlier than first trade tick
        self._instr = _instr()
        self._t0 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        kickoff_time = self._t0 - timedelta(seconds=1)
        self.add_event_feed("kick", FixedSequenceEventFeed([_KickoffEvent(kickoff_time)]))

    def on_event(self, event) -> None:
        if not self._submitted and isinstance(event, _KickoffEvent):
            instr = self._instr  # type: ignore[assignment]
            t0 = self._t0  # type: ignore[assignment]
            self.submit_order(MarketOrder(instr, OrderSide.SELL, D("1")), self._broker)
            self._submitted = True
            self.remove_event_feed("kick")

            # Now attach the first trade tick to produce the first order-book and fill
            ticks = [TradeTickEvent(TradeTick(instr, D("250"), D("10"), t0), t0)]
            self.add_event_feed("trades", FixedSequenceEventFeed(ticks), use_for_simulated_fills=True)

    def on_execution(self, execution) -> None:
        self.executions.append(execution)
        self.remove_event_feed("trades")


class _TradesTwoOrdersSameTickStrategy(Strategy):
    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self.executions = []
        self._submitted = False

    def on_start(self) -> None:
        instr = _instr()
        t0 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        ticks = [TradeTickEvent(TradeTick(instr, D("300"), D("10"), t0), t0)]
        self.add_event_feed("trades", FixedSequenceEventFeed(ticks), use_for_simulated_fills=True)

    def on_event(self, event) -> None:
        if not self._submitted:
            instr = event.trade_tick.instrument
            self.submit_order(MarketOrder(instr, OrderSide.BUY, D("1")), self._broker)
            self.submit_order(MarketOrder(instr, OrderSide.SELL, D("1")), self._broker)
            self._submitted = True

    def on_execution(self, execution) -> None:
        self.executions.append(execution)
        if len(self.executions) >= 2:
            self.remove_event_feed("trades")


class TestMarketOrderTradesBasic:
    def test_immediate_fill_at_last_trade_price(self):
        """Submitting on a trade tick should fill immediately at that last trade price (zero-spread model)."""
        engine = TradingEngine()
        broker = _create_optimistic_sim_broker()
        engine.add_broker("sim", broker)
        s = _TradesSubmitInCallbackStrategy("trades_cb", broker)
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) == 1
        e = s.executions[0]
        assert e.price == D("250")

    def test_submit_before_any_trade_fills_on_first_trade(self):
        """Submitting before trades exist should fill on the first trade tick when it arrives."""
        engine = TradingEngine()
        broker = _create_optimistic_sim_broker()
        engine.add_broker("sim", broker)
        s = _TradesSubmitBeforeTicksStrategy("trades_before", broker)
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) == 1
        assert s.executions[0].price == D("250")

    def test_two_orders_same_tick_both_fill(self):
        """Two opposite orders on the same trade tick should both fill at that tick's price; both callbacks recorded."""
        engine = TradingEngine()
        broker = _create_optimistic_sim_broker()
        engine.add_broker("sim", broker)
        s = _TradesTwoOrdersSameTickStrategy("trades_two", broker)
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) == 2
