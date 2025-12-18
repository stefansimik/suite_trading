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
from suite_trading.utils.data_generation.assistant import DGA
from suite_trading.domain.market_data.tick.quote_tick_event import QuoteTickEvent
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.event import Event


def _make_instr() -> Instrument:
    return DGA.instrument.create_fx_spot_eurusd()


def _create_optimistic_sim_broker() -> SimBroker:
    fill_model = DistributionFillModel(market_fill_adjustment_distribution={0: D("1")}, limit_on_touch_fill_probability=D("1"), rng_seed=42)
    return SimBroker(fill_model=fill_model)


class _QuotesSubmitInCallbackStrategy(Strategy):
    """Submits BUY and SELL inside first tick callback (fills at ask/bid)."""

    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self.executions = []
        self._submitted = False

    def on_start(self) -> None:
        instr = _make_instr()
        t0 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        ticks = [QuoteTickEvent(DGA.quote_ticks.create_quote_tick_from_strings(instr, "1.0000@5", "1.0001@5", t0), t0)]
        self.add_event_feed("quotes", FixedSequenceEventFeed(ticks), use_for_simulated_fills=True)

    def on_event(self, event) -> None:
        if not self._submitted:
            instr = event.quote_tick.instrument
            self.submit_order(MarketOrder(instr, OrderSide.BUY, D("1")), self._broker)
            self.submit_order(MarketOrder(instr, OrderSide.SELL, D("1")), self._broker)
            self._submitted = True

    def on_execution(self, execution) -> None:
        self.executions.append(execution)
        if len(self.executions) >= 2:
            self.remove_event_feed("quotes")


class _KickoffEvent(Event):
    """Non-convertible event used to submit while RUNNING before any order-book exists."""

    def __init__(self, dt: datetime) -> None:
        super().__init__(dt_event=dt, dt_received=dt)


class _QuotesSubmitBeforeTicksStrategy(Strategy):
    """Submits BUY before any quote arrives (fills on first quote at ask)."""

    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self.executions = []
        self._submitted = False
        self._instr: Instrument | None = None
        self._t0: datetime | None = None

    def on_start(self) -> None:
        # Defer submission until RUNNING via kickoff event occurring before the first quote tick
        self._instr = _make_instr()
        self._t0 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        kickoff_time = self._t0 - timedelta(seconds=1)
        self.add_event_feed("kick", FixedSequenceEventFeed([_KickoffEvent(kickoff_time)]))

    def on_event(self, event) -> None:
        if not self._submitted and isinstance(event, _KickoffEvent):
            instr = self._instr  # type: ignore[assignment]
            t0 = self._t0  # type: ignore[assignment]
            self.submit_order(MarketOrder(instr, OrderSide.BUY, D("1")), self._broker)
            self._submitted = True
            self.remove_event_feed("kick")

            ticks = [QuoteTickEvent(DGA.quote_ticks.create_quote_tick_from_strings(instr, "1.0000@5", "1.0001@5", t0), t0)]
            self.add_event_feed("quotes", FixedSequenceEventFeed(ticks), use_for_simulated_fills=True)

    def on_execution(self, execution) -> None:
        self.executions.append(execution)
        self.remove_event_feed("quotes")


class _QuotesPartialAcrossTicksStrategy(Strategy):
    """Submits BUY 2 before quotes; fills 1 on first tick, 1 on second tick."""

    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self.executions = []
        self._submitted = False
        self._instr: Instrument | None = None
        self._t0: datetime | None = None

    def on_start(self) -> None:
        # Defer submission until RUNNING via kickoff event occurring before first quote tick
        self._instr = _make_instr()
        self._t0 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        kickoff_time = self._t0 - timedelta(seconds=1)
        self.add_event_feed("kick", FixedSequenceEventFeed([_KickoffEvent(kickoff_time)]))

    def on_event(self, event) -> None:
        if not self._submitted and isinstance(event, _KickoffEvent):
            instr = self._instr  # type: ignore[assignment]
            t0 = self._t0  # type: ignore[assignment]
            self.submit_order(MarketOrder(instr, OrderSide.BUY, D("2")), self._broker)
            self._submitted = True
            self.remove_event_feed("kick")

            t1 = t0 + timedelta(seconds=1)
            ticks = [
                QuoteTickEvent(DGA.quote_ticks.create_quote_tick_from_strings(instr, "1.0000@5", "1.0001@1", t0), t0),
                QuoteTickEvent(DGA.quote_ticks.create_quote_tick_from_strings(instr, "1.0000@5", "1.0002@1", t1), t1),
            ]
            self.add_event_feed("quotes", FixedSequenceEventFeed(ticks), use_for_simulated_fills=True)

    def on_execution(self, execution) -> None:
        self.executions.append(execution)
        if len(self.executions) >= 2:
            self.remove_event_feed("quotes")


class TestMarketOrderQuotesBasic:
    def test_buy_hits_ask_sell_hits_bid_immediately(self):
        """Submitting BUY and SELL on the same quote tick should fill at ask and bid respectively, immediately."""
        engine = TradingEngine()
        broker = _create_optimistic_sim_broker()
        engine.add_broker("sim", broker)
        s = _QuotesSubmitInCallbackStrategy("quotes_cb", broker)
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) == 2
        buy_exec = next(e for e in s.executions if e.order.side == OrderSide.BUY)
        sell_exec = next(e for e in s.executions if e.order.side == OrderSide.SELL)
        assert buy_exec.price == D("1.0001")
        assert sell_exec.price == D("1.0000")

    def test_submit_before_any_quote_fills_on_first_quote(self):
        """Submitting before any quotes exist should fill on the first quote's ask when it arrives."""
        engine = TradingEngine()
        broker = _create_optimistic_sim_broker()
        engine.add_broker("sim", broker)
        s = _QuotesSubmitBeforeTicksStrategy("quotes_before", broker)
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) == 1
        assert s.executions[0].price == D("1.0001")

    def test_partial_fill_across_successive_quote_ticks(self):
        """BUY 2 with only 1 available per tick should fill 1 on the first tick and 1 on the next at its ask."""
        engine = TradingEngine()
        broker = _create_optimistic_sim_broker()
        engine.add_broker("sim", broker)
        s = _QuotesPartialAcrossTicksStrategy("quotes_partial", broker)
        engine.add_strategy(s)

        engine.start()

        assert [(e.quantity, e.price) for e in s.executions] == [(D("1"), D("1.0001")), (D("1"), D("1.0002"))]
