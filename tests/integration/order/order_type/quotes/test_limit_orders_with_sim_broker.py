from __future__ import annotations

from decimal import Decimal
from typing import Callable

from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.platform.engine.models.event_to_order_book.default_impl import DefaultEventToOrderBookConverter

from suite_trading.domain.order.orders import LimitOrder, Order, MarketOrder  # noqa: F401 (MarketOrder kept for parity with other tests)
from suite_trading.domain.order.order_state import OrderState

from suite_trading.domain.market_data.tick.quote_tick_event import QuoteTickEvent

from suite_trading.domain.instrument import Instrument
from suite_trading.utils.datetime_tools import make_utc
from suite_trading.utils.data_generation.assistant import DGA


class _LimitOrderTestStrategy(Strategy):
    """Minimal strategy used by tests to submit one LimitOrder on first event.

    Flow:
    - on_start(): adds a FixedSequenceEventFeed provided via constructor
    - on_event(): submits exactly one order created by $order_factory and optionally removes the feed
    """

    def __init__(self, name: str, broker: SimBroker, feed_name: str, quote_tick_events: list[QuoteTickEvent], order_factory: Callable[[QuoteTickEvent], Order], *, remove_feed_after_submit: bool) -> None:
        super().__init__(name)
        self._broker = broker
        self._feed_name = feed_name
        self._quote_tick_events = quote_tick_events
        self._order_factory = order_factory
        self._remove_feed_after_submit = remove_feed_after_submit
        self._submitted_order: Order | None = None

    def on_start(self) -> None:
        feed = FixedSequenceEventFeed(self._quote_tick_events)
        self.add_event_feed(self._feed_name, feed, use_for_simulated_fills=True)

    def on_event(self, event) -> None:
        # Submit exactly once on the first QuoteTickEvent; use reference presence as the guard
        if isinstance(event, QuoteTickEvent) and self._submitted_order is None:
            order = self._order_factory(event)
            self.submit_order(order, self._broker)
            self._submitted_order = order
            if self._remove_feed_after_submit:
                self.remove_event_feed(self._feed_name)

    @property
    def submitted_order(self) -> Order | None:
        """Return the single order this strategy submitted (or None if not yet submitted)."""
        return self._submitted_order


def _create_us_equity_instrument() -> Instrument:
    return DGA.instrument.equity_aapl()


def _create_quote_tick_event(instrument: Instrument, *, bid: str, ask: str, timestamp_index: int = 0) -> QuoteTickEvent:
    # Use deterministic UTC timestamps separated by seconds to preserve ordering
    ts = make_utc(2025, 1, 1, 12, 0, 0 + timestamp_index)
    tick = DGA.quote_tick.from_strings(instrument, bid, ask, ts)
    return QuoteTickEvent(tick, ts)


def _create_sim_broker_with_deterministic_fill_model() -> SimBroker:
    fill_model = DistributionFillModel(market_fill_adjustment_distribution={0: Decimal("1")}, limit_on_touch_fill_probability=Decimal("1"), rng_seed=42)
    return SimBroker(fill_model=fill_model)


def test_limit_buy_crossing_best_ask_fills_immediately() -> None:
    # Arrange: engine + broker + converter
    engine = TradingEngine()
    broker = _create_sim_broker_with_deterministic_fill_model()
    engine.add_broker("sim", broker)
    engine.set_order_book_converter(DefaultEventToOrderBookConverter())

    instrument = _create_us_equity_instrument()
    # One quote where best ask is 100.00; BUY limit with price above ask is marketable and should fill immediately
    quote_tick_events = [_create_quote_tick_event(instrument, bid="99.97@5", ask="100.00@5", timestamp_index=0)]

    def create_limit_order(_: QuoteTickEvent) -> Order:
        return LimitOrder(instrument=instrument, signed_qty=1, limit_price=100.01)

    limit_order_strategy = _LimitOrderTestStrategy(name="limit_reject", broker=broker, feed_name="prices", quote_tick_events=quote_tick_events, order_factory=create_limit_order, remove_feed_after_submit=True)
    engine.add_strategy(limit_order_strategy)

    # Act
    engine.start()

    # Assert: marketable limit order fills immediately and becomes terminal
    assert len(broker.list_active_orders()) == 0
    order_fills = engine.list_order_fills_for_strategy("limit_reject")
    assert len(order_fills) == 1
    assert order_fills[0].order.is_fully_filled
    assert order_fills[0].price == Decimal("100.00")
    submitted_order = limit_order_strategy.submitted_order
    assert submitted_order is not None
    assert submitted_order.state == OrderState.FILLED


def test_limit_instant_fill_touch() -> None:
    # Arrange
    engine = TradingEngine()
    broker = _create_sim_broker_with_deterministic_fill_model()
    engine.add_broker("sim", broker)
    engine.set_order_book_converter(DefaultEventToOrderBookConverter())

    instrument = _create_us_equity_instrument()
    # One quote with ask exactly at 99.98; BUY limit at 99.98 should be accepted and filled in one proposed fill
    quote_tick_events = [_create_quote_tick_event(instrument, bid="99.95@5", ask="99.98@5", timestamp_index=0)]

    def create_limit_order(_: QuoteTickEvent) -> Order:
        return LimitOrder(instrument=instrument, signed_qty=1, limit_price=99.98)

    limit_order_strategy = _LimitOrderTestStrategy(name="limit_instant_fill", broker=broker, feed_name="prices", quote_tick_events=quote_tick_events, order_factory=create_limit_order, remove_feed_after_submit=True)
    engine.add_strategy(limit_order_strategy)

    # Act
    engine.start()

    # Assert: filled once and terminal
    assert len(broker.list_active_orders()) == 0
    order_fills = engine.list_order_fills_for_strategy("limit_instant_fill")
    assert len(order_fills) == 1
    assert order_fills[0].order.is_fully_filled
    assert order_fills[0].price == Decimal("99.98")


def test_limit_multiple_partial_fills() -> None:
    # Arrange
    engine = TradingEngine()
    broker = _create_sim_broker_with_deterministic_fill_model()
    engine.add_broker("sim", broker)
    engine.set_order_book_converter(DefaultEventToOrderBookConverter())

    instrument = _create_us_equity_instrument()
    # Three ticks with ask <= 100.00 and volume 1 each to force 3 partial fills
    quote_tick_events = [
        _create_quote_tick_event(instrument, bid="99.95@5", ask="100.00@1", timestamp_index=0),
        _create_quote_tick_event(instrument, bid="99.96@5", ask="99.99@1", timestamp_index=1),
        _create_quote_tick_event(instrument, bid="99.97@5", ask="99.98@1", timestamp_index=2),
    ]

    def create_limit_order(_: QuoteTickEvent) -> Order:
        return LimitOrder(instrument=instrument, signed_qty=3, limit_price=100.00)

    limit_order_strategy = _LimitOrderTestStrategy(name="limit_partials", broker=broker, feed_name="fill_prices", quote_tick_events=quote_tick_events, order_factory=create_limit_order, remove_feed_after_submit=False)
    engine.add_strategy(limit_order_strategy)

    # Act
    engine.start()

    # Assert: three order_fills with fill_prices following the feed and total abs_qty 3
    assert len(broker.list_active_orders()) == 0
    order_fills = engine.list_order_fills_for_strategy("limit_partials")
    assert len(order_fills) == 3
    total_filled_quantity = sum(e.abs_quantity for e in order_fills)
    assert total_filled_quantity == Decimal("3")
    fill_prices = [e.price for e in order_fills]
    assert fill_prices == [Decimal("100.00"), Decimal("99.99"), Decimal("99.98")]
