from __future__ import annotations

from decimal import Decimal
from typing import Callable

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick
from suite_trading.domain.market_data.tick.quote_tick_event import QuoteTickEvent
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.domain.order.order_state import OrderState
from suite_trading.domain.order.orders import Order, StopLimitOrder, StopMarketOrder
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.engine.models.event_to_order_book.default_impl import DefaultEventToOrderBookConverter
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.strategy.strategy import Strategy
from suite_trading.utils.data_generation.assistant import DGA
from suite_trading.utils.datetime_tools import make_utc


class _StopLikeOrderLifecycleStrategy(Strategy):
    """Minimal strategy that submits exactly one stop-like order and records broker lifecycle states."""

    def __init__(
        self,
        name: str,
        broker: SimBroker,
        feed_name: str,
        quote_tick_events: list[QuoteTickEvent],
        order_factory: Callable[[], Order],
    ) -> None:
        super().__init__(name)
        self._broker = broker
        self._feed_name = feed_name
        self._quote_tick_events = quote_tick_events
        self._order_factory = order_factory
        self._submitted_order: Order | None = None
        self._observed_states: list[OrderState] = []

    def on_start(self) -> None:
        feed = FixedSequenceEventFeed(self._quote_tick_events)
        self.add_event_feed(self._feed_name, feed, use_for_simulated_fills=True)

    def on_event(self, event) -> None:
        if isinstance(event, QuoteTickEvent) and self._submitted_order is None:
            order = self._order_factory()
            self._submitted_order = order
            self.submit_order(order, self._broker)

    def on_order_updated(self, order: Order) -> None:
        submitted = self._submitted_order
        if submitted is None:
            return
        if order.id != submitted.id:
            return
        self._observed_states.append(order.state)

    @property
    def submitted_order(self) -> Order | None:
        return self._submitted_order

    @property
    def observed_states(self) -> list[OrderState]:
        return self._observed_states


def _create_quote_tick_event(
    instrument: Instrument,
    *,
    bid: str,
    ask: str,
    bid_volume: str = "5",
    ask_volume: str = "5",
    timestamp_index: int,
) -> QuoteTickEvent:
    ts = make_utc(2025, 1, 1, 12, 0, 0 + timestamp_index)
    tick = QuoteTick(instrument, Decimal(bid), Decimal(ask), Decimal(bid_volume), Decimal(ask_volume), ts)
    result = QuoteTickEvent(tick, ts)
    return result


def _create_sim_broker_with_deterministic_fill_model() -> SimBroker:
    fill_model = DistributionFillModel(market_fill_adjustment_distribution={0: Decimal("1")}, limit_on_touch_fill_probability=Decimal("1"), rng_seed=42)
    result = SimBroker(fill_model=fill_model)
    return result


def _assert_state_order(states: list[OrderState], first: OrderState, second: OrderState) -> None:
    assert first in states, f"Expected $states to include {first}"
    assert second in states, f"Expected $states to include {second}"
    assert states.index(first) < states.index(second), f"Expected {first} to occur before {second}"


def test_stop_market_order_arms_triggers_and_fills_on_next_quote_tick() -> None:
    # Arrange: engine + broker + converter
    engine = TradingEngine()
    broker = _create_sim_broker_with_deterministic_fill_model()
    engine.add_broker("sim", broker)
    engine.set_order_book_converter(DefaultEventToOrderBookConverter())

    instrument = DGA.instrument.create_equity_aapl()
    stop_price = Decimal("100.00")

    # Two ticks: first does not meet stop; second triggers and should fill immediately.
    quote_tick_events = [
        _create_quote_tick_event(instrument, bid="99.98", ask="99.99", timestamp_index=0),
        _create_quote_tick_event(instrument, bid="99.99", ask="100.00", timestamp_index=1),
    ]

    def create_order() -> Order:
        return StopMarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("1"), stop_price=stop_price)

    strategy = _StopLikeOrderLifecycleStrategy(name="stop_market_order_lifecycle", broker=broker, feed_name="quotes", quote_tick_events=quote_tick_events, order_factory=create_order)
    engine.add_strategy(strategy)

    # Act
    engine.start()

    # Assert: order is filled and cleaned up
    assert len(broker.list_active_orders()) == 0
    executions = engine.list_executions_for_strategy("stop_market_order_lifecycle")
    assert len(executions) == 1
    assert executions[0].order.is_fully_filled
    assert executions[0].price == Decimal("100.00")

    submitted_order = strategy.submitted_order
    assert submitted_order is not None
    assert submitted_order.state == OrderState.FILLED

    # Assert: lifecycle includes arm -> trigger -> working -> filled
    states = strategy.observed_states
    _assert_state_order(states, OrderState.TRIGGER_PENDING, OrderState.TRIGGERED)
    _assert_state_order(states, OrderState.TRIGGERED, OrderState.WORKING)
    _assert_state_order(states, OrderState.WORKING, OrderState.FILLED)


def test_stop_limit_order_arms_triggers_and_fills_on_next_quote_tick() -> None:
    # Arrange: engine + broker + converter
    engine = TradingEngine()
    broker = _create_sim_broker_with_deterministic_fill_model()
    engine.add_broker("sim", broker)
    engine.set_order_book_converter(DefaultEventToOrderBookConverter())

    instrument = DGA.instrument.create_equity_aapl()
    stop_price = Decimal("100.00")
    limit_price = Decimal("100.01")

    # Two ticks: first does not meet stop; second triggers and should fill (marketable after trigger).
    quote_tick_events = [
        _create_quote_tick_event(instrument, bid="99.98", ask="99.99", timestamp_index=0),
        _create_quote_tick_event(instrument, bid="99.99", ask="100.00", timestamp_index=1),
    ]

    def create_order() -> Order:
        return StopLimitOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("1"), stop_price=stop_price, limit_price=limit_price)

    strategy = _StopLikeOrderLifecycleStrategy(name="stop_limit_order_lifecycle", broker=broker, feed_name="quotes", quote_tick_events=quote_tick_events, order_factory=create_order)
    engine.add_strategy(strategy)

    # Act
    engine.start()

    # Assert: order is filled and cleaned up
    assert len(broker.list_active_orders()) == 0
    executions = engine.list_executions_for_strategy("stop_limit_order_lifecycle")
    assert len(executions) == 1
    assert executions[0].order.is_fully_filled
    assert executions[0].price == Decimal("100.00")

    submitted_order = strategy.submitted_order
    assert submitted_order is not None
    assert submitted_order.state == OrderState.FILLED

    # Assert: lifecycle includes arm -> trigger -> working -> filled
    states = strategy.observed_states
    _assert_state_order(states, OrderState.TRIGGER_PENDING, OrderState.TRIGGERED)
    _assert_state_order(states, OrderState.TRIGGERED, OrderState.WORKING)
    _assert_state_order(states, OrderState.WORKING, OrderState.FILLED)
