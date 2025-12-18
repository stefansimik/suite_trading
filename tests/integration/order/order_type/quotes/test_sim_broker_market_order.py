from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal as D

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.event import Event
from suite_trading.domain.market_data.tick.quote_tick_event import QuoteTickEvent
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.domain.order.orders import MarketOrder
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.utils.data_generation.assistant import DGA


class TestSimBrokerMarketOrder:
    """Market orders fill using the latest order-book snapshot through the full engine pipeline."""

    def _create_optimistic_sim_broker(self) -> SimBroker:
        fill_model = DistributionFillModel(market_fill_adjustment_distribution={0: D("1")}, limit_on_touch_fill_probability=D("1"), rng_seed=42)
        return SimBroker(fill_model=fill_model)

    def _instrument(self) -> Instrument:
        return DGA.instrument.equity_aapl()

    def _ts(self, seconds: int = 0) -> datetime:
        base = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        return base.replace(second=seconds)

    # region Local Strategy stubs

    class _KickoffEvent(Event):
        """Non-convertible event used to submit while no order-book exists yet."""

        def __init__(self, dt: datetime) -> None:
            super().__init__(dt_event=dt, dt_received=dt)

    class _SubmitBeforeAnySnapshotStrategy(Strategy):
        """Submit a BUY at start when no order-books exist; then feed one quote to trigger the fill."""

        def __init__(self, name: str, broker: SimBroker, instrument: Instrument, price: D, ts: datetime) -> None:
            super().__init__(name)
            self._broker = broker
            self._instrument = instrument
            self._price = price
            self._ts = ts
            self.executions = []

        def on_start(self) -> None:
            # Add a non-convertible kickoff event first; we will submit in its callback (state RUNNING, no order-book yet)
            kickoff_time = self._ts - timedelta(seconds=1)
            self.add_event_feed("kick", FixedSequenceEventFeed([TestSimBrokerMarketOrder._KickoffEvent(kickoff_time)]))

        def on_execution(self, execution) -> None:
            self.executions.append(execution)
            self.remove_event_feed("q")

        def on_event(self, event) -> None:
            # Submit in the kickoff event callback (no order-book exists yet), then attach the first quote tick feed
            if isinstance(event, TestSimBrokerMarketOrder._KickoffEvent):
                self.submit_order(MarketOrder(self._instrument, OrderSide.BUY, D("1")), self._broker)
                self.remove_event_feed("kick")

                # Now add a single-quote feed to produce the first order-book
                tick = DGA.quote_tick.from_strings(self._instrument, f"{self._price - D('1')}@5", f"{self._price}@5", self._ts)
                self.add_event_feed("q", FixedSequenceEventFeed([QuoteTickEvent(tick, self._ts)]), use_for_simulated_fills=True)

    class _SubmitWhenSnapshotExistsStrategy(Strategy):
        """Create a quote first, then submit inside callback so an order-book exists on submit."""

        def __init__(self, name: str, broker: SimBroker, instrument: Instrument, ask_price: D, ts: datetime) -> None:
            super().__init__(name)
            self._broker = broker
            self._instrument = instrument
            self._ask = ask_price
            self._ts = ts
            self._submitted = False
            self.executions = []

        def on_start(self) -> None:
            tick = DGA.quote_tick.from_strings(self._instrument, f"{self._ask - D('2')}@5", f"{self._ask}@5", self._ts)
            self.add_event_feed("q", FixedSequenceEventFeed([QuoteTickEvent(tick, self._ts)]), use_for_simulated_fills=True)

        def on_event(self, event) -> None:
            if not self._submitted:
                self.submit_order(MarketOrder(self._instrument, OrderSide.BUY, D("1")), self._broker)
                self._submitted = True

        def on_execution(self, execution) -> None:
            self.executions.append(execution)
            self.remove_event_feed("q")

    class _PartialAcrossSuccessiveSnapshotsStrategy(Strategy):
        """Submit BUY 3 before quotes; three quote ticks with ask=100/101/102 and vol=1 each fill in three slices."""

        def __init__(self, name: str, broker: SimBroker, instrument: Instrument, t0: datetime) -> None:
            super().__init__(name)
            self._broker = broker
            self._instrument = instrument
            self._t0 = t0
            self.executions = []

        def on_start(self) -> None:
            kickoff_time = self._t0 - timedelta(seconds=1)
            self.add_event_feed("kick", FixedSequenceEventFeed([TestSimBrokerMarketOrder._KickoffEvent(kickoff_time)]))

        def on_execution(self, execution) -> None:
            self.executions.append(execution)
            if len(self.executions) >= 3:
                self.remove_event_feed("q")

        def on_event(self, event) -> None:
            if isinstance(event, TestSimBrokerMarketOrder._KickoffEvent):
                # Submit before any order-book exists; then attach three successive quote ticks
                self.submit_order(MarketOrder(self._instrument, OrderSide.BUY, D("3")), self._broker)
                self.remove_event_feed("kick")

                t0 = self._t0
                ticks = [
                    QuoteTickEvent(DGA.quote_tick.from_strings(self._instrument, "99@5", "100@1", t0), t0),
                    QuoteTickEvent(DGA.quote_tick.from_strings(self._instrument, "100@5", "101@1", t0 + timedelta(seconds=1)), t0 + timedelta(seconds=1)),
                    QuoteTickEvent(DGA.quote_tick.from_strings(self._instrument, "101@5", "102@1", t0 + timedelta(seconds=2)), t0 + timedelta(seconds=2)),
                ]
                self.add_event_feed("q", FixedSequenceEventFeed(ticks), use_for_simulated_fills=True)

    class _PartialCompletesOnNextSnapshotStrategy(Strategy):
        """Submit BUY 2; first tick has ask vol=1@100, next tick 1@101 → two slices across snapshots."""

        def __init__(self, name: str, broker: SimBroker, instrument: Instrument, t0: datetime) -> None:
            super().__init__(name)
            self._broker = broker
            self._instrument = instrument
            self._t0 = t0
            self.executions = []

        def on_start(self) -> None:
            kickoff_time = self._t0 - timedelta(seconds=1)
            self.add_event_feed("kick", FixedSequenceEventFeed([TestSimBrokerMarketOrder._KickoffEvent(kickoff_time)]))

        def on_execution(self, execution) -> None:
            self.executions.append(execution)
            if len(self.executions) >= 2:
                self.remove_event_feed("q")

        def on_event(self, event) -> None:
            if isinstance(event, TestSimBrokerMarketOrder._KickoffEvent):
                # Submit before any order-book exists; then attach two successive quote ticks
                self.submit_order(MarketOrder(self._instrument, OrderSide.BUY, D("2")), self._broker)
                self.remove_event_feed("kick")

                t0 = self._t0
                ticks = [
                    QuoteTickEvent(DGA.quote_tick.from_strings(self._instrument, "99@5", "100@1", t0), t0),
                    QuoteTickEvent(DGA.quote_tick.from_strings(self._instrument, "100@5", "101@1", t0 + timedelta(seconds=1)), t0 + timedelta(seconds=1)),
                ]
                self.add_event_feed("q", FixedSequenceEventFeed(ticks), use_for_simulated_fills=True)

    class _TimestampEqualsSnapshotStrategy(Strategy):
        """Submit SELL inside first tick callback; expect execution timestamp equals that order-book's timestamp."""

        def __init__(self, name: str, broker: SimBroker, instrument: Instrument, ask: D, ts: datetime) -> None:
            super().__init__(name)
            self._broker = broker
            self._instrument = instrument
            self._ask = ask
            self._ts = ts
            self._submitted = False
            self.executions = []

        def on_start(self) -> None:
            tick = DGA.quote_tick.from_strings(self._instrument, f"{self._ask - D('1')}@5", f"{self._ask}@5", self._ts)
            self.add_event_feed("q", FixedSequenceEventFeed([QuoteTickEvent(tick, self._ts)]), use_for_simulated_fills=True)

        def on_event(self, event) -> None:
            if not self._submitted:
                self.submit_order(MarketOrder(self._instrument, OrderSide.SELL, D("2")), self._broker)
                self._submitted = True

        def on_execution(self, execution) -> None:
            self.executions.append(execution)
            self.remove_event_feed("q")

    # endregion

    def test_submit_before_any_book_fills_on_first_book(self):
        """Submit BUY before any order-book exists; fill should happen on the first arriving order-book (ask/time)."""
        instr = self._instrument()
        broker = self._create_optimistic_sim_broker()
        engine = TradingEngine()
        engine.add_broker("sim", broker)
        s = self._SubmitBeforeAnySnapshotStrategy("s_before", broker, instr, D("100"), self._ts(1))
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) == 1 and s.executions[0].price == D("100") and s.executions[0].timestamp == self._ts(1)

    def test_immediate_fill_when_book_exists(self):
        """If an order-book exists on submit, Market order fills immediately at best ask with that snapshot's timestamp."""
        instr = self._instrument()
        broker = self._create_optimistic_sim_broker()
        engine = TradingEngine()
        engine.add_broker("sim", broker)
        s = self._SubmitWhenSnapshotExistsStrategy("s_immediate", broker, instr, D("101"), self._ts(2))
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) == 1 and s.executions[0].price == D("101") and s.executions[0].timestamp == self._ts(2)

    def test_partial_fill_across_multiple_levels(self):
        """Three successive order-books with 1 lot each at 100/101/102 should fill BUY 3 in three slices."""
        instr = self._instrument()
        broker = self._create_optimistic_sim_broker()
        engine = TradingEngine()
        engine.add_broker("sim", broker)
        s = self._PartialAcrossSuccessiveSnapshotsStrategy("s_partial_levels", broker, instr, self._ts(3))
        engine.add_strategy(s)

        engine.start()

        pairs = [(e.quantity, e.price) for e in s.executions]
        assert pairs == [(D("1"), D("100")), (D("1"), D("101")), (D("1"), D("102"))]

    def test_partial_fill_completes_on_next_book(self):
        """Not enough depth now: fill 1@100, remain working, and complete on next snapshot 1@101."""
        instr = self._instrument()
        broker = self._create_optimistic_sim_broker()
        engine = TradingEngine()
        engine.add_broker("sim", broker)
        s = self._PartialCompletesOnNextSnapshotStrategy("s_partial_next", broker, instr, self._ts(4))
        engine.add_strategy(s)

        engine.start()

        pairs = [(e.quantity, e.price) for e in s.executions]
        assert pairs == [(D("1"), D("100")), (D("1"), D("101"))]

    def test_execution_timestamp_equals_order_book_timestamp(self):
        """Execution timestamp must equal the OrderBook timestamp used for matching."""
        instr = self._instrument()
        broker = self._create_optimistic_sim_broker()
        engine = TradingEngine()
        engine.add_broker("sim", broker)
        ts = self._ts(6)
        s = self._TimestampEqualsSnapshotStrategy("s_ts", broker, instr, D("101"), ts)
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) == 1 and s.executions[0].timestamp == ts
