from __future__ import annotations

from decimal import Decimal as D
from datetime import datetime, timedelta

from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.strategy.strategy import Strategy
from suite_trading.domain.order.orders import MarketOrder
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.domain.market_data.bar.bar_event import wrap_bars_to_events
from suite_trading.domain.event import Event
from suite_trading.utils.data_generation.assistant import DGA


def _create_optimistic_sim_broker() -> SimBroker:
    fill_model = DistributionFillModel(market_fill_adjustment_distribution={0: D("1")}, limit_on_touch_fill_probability=D("1"), rng_seed=42)
    return SimBroker(fill_model=fill_model)


class _KickoffEvent(Event):
    """Non-convertible event used to submit while RUNNING before any order-book exists."""

    def __init__(self, dt: datetime) -> None:
        super().__init__(dt_event=dt, dt_received=dt)


class _BarsSubmitAtStartStrategy(Strategy):
    """Submits a Market BUY before any bar are delivered (fills on first OPEN)."""

    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self._bars: list | None = None
        self._submitted = False
        self.order_fills = []

    def on_start(self) -> None:
        # Prepare bar series but submit only when RUNNING using a kickoff event before first bar
        self._bars = DGA.bar.create_series(num_bars=5)
        first_start = self._bars[0].start_dt
        kickoff_time = first_start - timedelta(seconds=1)
        self.add_event_feed("kick", FixedSequenceEventFeed([_KickoffEvent(kickoff_time)]))

    def on_event(self, event) -> None:
        # Submit in kickoff callback while no order-book exists yet; then attach bar feed
        if not self._submitted and isinstance(event, _KickoffEvent):
            assert self._bars is not None
            instr = self._bars[0].instrument
            order = MarketOrder(instr, OrderSide.BUY, D("1"))
            self.submit_order(order, self._broker)
            self._submitted = True
            self.remove_event_feed("kick")
            self.add_event_feed("bar", FixedSequenceEventFeed(wrap_bars_to_events(self._bars)), use_for_simulated_fills=True)

    def on_order_fill(self, order_fill) -> None:
        self.order_fills.append(order_fill)


class _BarsSubmitInsideCallbackStrategy(Strategy):
    """Submits inside first BarEvent callback (fills at that bar's CLOSE)."""

    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self._submitted = False
        self.order_fills = []

    def on_start(self) -> None:
        self._bars = DGA.bar.create_series(num_bars=5)
        self.add_event_feed("bar", FixedSequenceEventFeed(wrap_bars_to_events(self._bars)), use_for_simulated_fills=True)

    def on_event(self, event) -> None:
        if not self._submitted:
            instr = self._bars[0].instrument
            order = MarketOrder(instr, OrderSide.BUY, D("1"))
            self.submit_order(order, self._broker)
            self._submitted = True

    def on_order_fill(self, order_fill) -> None:
        self.order_fills.append(order_fill)
        # Stop after first order_fill
        self.remove_event_feed("bar")


class _BarsOpenCloseReverseStrategy(Strategy):
    """Opens 1 contract after bar 1, then CLOSES or REVERSES later."""

    def __init__(self, name: str, broker: SimBroker, mode: str):
        super().__init__(name)
        self._broker = broker
        self._mode = mode  # "close" or "reverse"
        self._count = 0
        self.order_fills = []

    def on_start(self) -> None:
        self._bars = DGA.bar.create_series(num_bars=5)
        self.add_event_feed("bar", FixedSequenceEventFeed(wrap_bars_to_events(self._bars)), use_for_simulated_fills=True)

    def on_event(self, event) -> None:
        self._count += 1
        instr = self._bars[0].instrument
        if self._count == 1:
            self.submit_order(MarketOrder(instr, OrderSide.BUY, D("1")), self._broker)
        elif self._count == 3:
            if self._mode == "close":
                self.submit_order(MarketOrder(instr, OrderSide.SELL, D("1")), self._broker)
            else:
                self.submit_order(MarketOrder(instr, OrderSide.SELL, D("2")), self._broker)

    def on_order_fill(self, order_fill) -> None:
        self.order_fills.append(order_fill)
        # Auto-stop when we have 2 order_fills for close, or 2 (open+reverse first leg) for reverse
        if len(self.order_fills) >= 2:
            self.remove_event_feed("bar")


class TestMarketOrderBarsBasic:
    def test_submit_before_first_bar_fills_on_open(self):
        """Submitting at start (no order-books yet) should fill on the first OPEN snapshot produced from bar 1."""
        engine = TradingEngine()
        broker = _create_optimistic_sim_broker()
        engine.add_broker("sim", broker)
        s = _BarsSubmitAtStartStrategy("bars_start", broker)
        engine.add_strategy(s)

        engine.start()

        assert len(s.order_fills) >= 1
        first_exec = s.order_fills[0]
        # Expect fill at OPEN of the first bar (converter emits OPEN first)
        bars = DGA.bar.create_series(num_bars=5)
        assert first_exec.price == bars[0].open
        assert first_exec.timestamp == bars[0].start_dt

    def test_submit_inside_first_bar_callback_fills_at_close(self):
        """Submit inside first BarEvent callback; engine processes OHLC before callback, so fill uses that bar's CLOSE."""
        engine = TradingEngine()
        broker = _create_optimistic_sim_broker()
        engine.add_broker("sim", broker)
        s = _BarsSubmitInsideCallbackStrategy("bars_in_cb", broker)
        engine.add_strategy(s)

        engine.start()

        assert len(s.order_fills) == 1
        bars = s._bars
        # Since engine processes OHLC before callback, immediate fill uses last processed snapshot (CLOSE)
        assert s.order_fills[0].price == bars[0].close
        assert s.order_fills[0].timestamp == bars[0].end_dt

    def test_open_then_close_and_reverse(self):
        """Open 1 on bar 1, then either close (SELL 1) or reverse (SELL 2); verify final position state for both flows."""
        # Close path
        engine = TradingEngine()
        broker = _create_optimistic_sim_broker()
        engine.add_broker("sim", broker)
        s_close = _BarsOpenCloseReverseStrategy("bars_close", broker, mode="close")
        engine.add_strategy(s_close)
        engine.start()
        assert len(s_close.order_fills) == 2
        assert broker.get_position_quantity(s_close.order_fills[0].order.instrument) == D("0")

        # Reverse path
        engine2 = TradingEngine()
        broker2 = _create_optimistic_sim_broker()
        engine2.add_broker("sim2", broker2)
        s_rev = _BarsOpenCloseReverseStrategy("bars_reverse", broker2, mode="reverse")
        engine2.add_strategy(s_rev)
        engine2.start()
        # After BUY 1 then SELL 2, final position should be short 1
        assert broker2.get_position_quantity(s_rev.order_fills[0].order.instrument) == D("-1")
