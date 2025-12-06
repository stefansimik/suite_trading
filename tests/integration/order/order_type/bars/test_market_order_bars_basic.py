from __future__ import annotations

from decimal import Decimal as D
from datetime import datetime, timedelta

from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.strategy.strategy import Strategy
from suite_trading.domain.order.orders import MarketOrder
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.domain.market_data.bar.bar_event import wrap_bars_to_events
from suite_trading.domain.event import Event
from suite_trading.utils.data_generation.assistant import DGA


class _KickoffEvent(Event):
    """Non-convertible event used to submit while RUNNING before any order-book exists."""

    def __init__(self, dt: datetime) -> None:
        super().__init__(dt_event=dt, dt_received=dt)


class _BarsSubmitAtStartStrategy(Strategy):
    """Submits a Market BUY before any bars are delivered (fills on first OPEN)."""

    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self._bars: list | None = None
        self._submitted = False
        self.executions = []

    def on_start(self) -> None:
        # Prepare bar series but submit only when RUNNING using a kickoff event before first bar
        self._bars = DGA.bars.create_bar_series(num_bars=5)
        first_start = self._bars[0].start_dt
        kickoff_time = first_start - timedelta(seconds=1)
        self.add_event_feed("kick", FixedSequenceEventFeed([_KickoffEvent(kickoff_time)]))

    def on_event(self, event) -> None:
        # Submit in kickoff callback while no order-book exists yet; then attach bars feed
        if not self._submitted and isinstance(event, _KickoffEvent):
            assert self._bars is not None
            instr = self._bars[0].instrument
            order = MarketOrder(instr, OrderSide.BUY, D("1"))
            self.submit_order(order, self._broker)
            self._submitted = True
            self.remove_event_feed("kick")
            self.add_event_feed("bars", FixedSequenceEventFeed(wrap_bars_to_events(self._bars)))

    def on_execution(self, execution) -> None:
        self.executions.append(execution)


class _BarsSubmitInsideCallbackStrategy(Strategy):
    """Submits inside first BarEvent callback (fills at that bar's CLOSE)."""

    def __init__(self, name: str, broker: SimBroker):
        super().__init__(name)
        self._broker = broker
        self._submitted = False
        self.executions = []

    def on_start(self) -> None:
        self._bars = DGA.bars.create_bar_series(num_bars=5)
        self.add_event_feed("bars", FixedSequenceEventFeed(wrap_bars_to_events(self._bars)))

    def on_event(self, event) -> None:
        if not self._submitted:
            instr = self._bars[0].instrument
            order = MarketOrder(instr, OrderSide.BUY, D("1"))
            self.submit_order(order, self._broker)
            self._submitted = True

    def on_execution(self, execution) -> None:
        self.executions.append(execution)
        # Stop after first execution
        self.remove_event_feed("bars")


class _BarsOpenCloseReverseStrategy(Strategy):
    """Opens 1 contract after bar 1, then CLOSES or REVERSES later."""

    def __init__(self, name: str, broker: SimBroker, mode: str):
        super().__init__(name)
        self._broker = broker
        self._mode = mode  # "close" or "reverse"
        self._count = 0
        self.executions = []

    def on_start(self) -> None:
        self._bars = DGA.bars.create_bar_series(num_bars=5)
        self.add_event_feed("bars", FixedSequenceEventFeed(wrap_bars_to_events(self._bars)))

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

    def on_execution(self, execution) -> None:
        self.executions.append(execution)
        # Auto-stop when we have 2 executions for close, or 2 (open+reverse first leg) for reverse
        if len(self.executions) >= 2:
            self.remove_event_feed("bars")


class TestMarketOrderBarsBasic:
    def test_submit_before_first_bar_fills_on_open(self):
        """Submitting at start (no order-books yet) should fill on the first OPEN snapshot produced from bar 1."""
        engine = TradingEngine()
        broker = SimBroker()
        engine.add_broker("sim", broker)
        s = _BarsSubmitAtStartStrategy("bars_start", broker)
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) >= 1
        first_exec = s.executions[0]
        # Expect fill at OPEN of the first bar (converter emits OPEN first)
        bars = DGA.bars.create_bar_series(num_bars=5)
        assert first_exec.price == bars[0].open
        assert first_exec.timestamp == bars[0].start_dt

    def test_submit_inside_first_bar_callback_fills_at_close(self):
        """Submit inside first BarEvent callback; engine processes OHLC before callback, so fill uses that bar's CLOSE."""
        engine = TradingEngine()
        broker = SimBroker()
        engine.add_broker("sim", broker)
        s = _BarsSubmitInsideCallbackStrategy("bars_in_cb", broker)
        engine.add_strategy(s)

        engine.start()

        assert len(s.executions) == 1
        bars = s._bars
        # Since engine processes OHLC before callback, immediate fill uses last processed snapshot (CLOSE)
        assert s.executions[0].price == bars[0].close
        assert s.executions[0].timestamp == bars[0].end_dt

    def test_open_then_close_and_reverse(self):
        """Open 1 on bar 1, then either close (SELL 1) or reverse (SELL 2); verify final position state for both flows."""
        # Close path
        engine = TradingEngine()
        broker = SimBroker()
        engine.add_broker("sim", broker)
        s_close = _BarsOpenCloseReverseStrategy("bars_close", broker, mode="close")
        engine.add_strategy(s_close)
        engine.start()
        assert len(s_close.executions) == 2
        pos = broker.get_position(s_close.executions[0].order.instrument)
        assert pos is None or pos.is_flat

        # Reverse path
        engine2 = TradingEngine()
        broker2 = SimBroker()
        engine2.add_broker("sim2", broker2)
        s_rev = _BarsOpenCloseReverseStrategy("bars_reverse", broker2, mode="reverse")
        engine2.add_strategy(s_rev)
        engine2.start()
        # After BUY 1 then SELL 2, final position should be short 1
        pos2 = broker2.get_position(s_rev.executions[0].order.instrument)
        assert pos2 is not None and pos2.is_short and pos2.quantity == D("-1")
