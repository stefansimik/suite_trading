from __future__ import annotations

from decimal import Decimal

from suite_trading.domain.market_data.order_book.order_book import OrderBook
from suite_trading.domain.market_data.order_book.order_book_event import OrderBookEvent, wrap_order_books_to_events
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.domain.order.orders import LimitOrder
from suite_trading.domain.order.order_state import OrderState
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.strategy.strategy import Strategy
from tests.helpers.test_assistant import TEST_ASSISTANT as TST


class SingleLimitOrderOrderBookStrategy(Strategy):
    """Strategy that submits a single BUY Limit order on first OrderBookEvent.

    The strategy attaches an OrderBook-based event-feed on start. When the first
    OrderBookEvent arrives, it submits a BUY Limit order with price 101 and
    quantity 10 using the provided SimBroker. This setup is intended for
    debugging how a Limit order interacts with a specific OrderBook snapshot.
    """

    def __init__(self, name: str, broker: SimBroker, instrument, order_books: list[OrderBook]) -> None:
        super().__init__(name)
        self._broker = broker
        self._instrument = instrument
        self._order_books = order_books
        self._feed_name = "order_book_feed"

        # Exposed for debugging in tests
        self.submitted_order: LimitOrder | None = None
        self.last_order_book_event: OrderBookEvent | None = None

    def on_start(self) -> None:
        # Attach a FixedSequenceEventFeed that emits the provided OrderBook snapshot(s)
        feed = FixedSequenceEventFeed(wrap_order_books_to_events(self._order_books))
        self.add_event_feed(self._feed_name, feed)

    def on_event(self, event) -> None:  # type: ignore[override]
        if isinstance(event, OrderBookEvent):
            self.last_order_book_event = event

            # Submit the Limit order only once, on the first OrderBookEvent
            if self.submitted_order is None:
                order = LimitOrder(instrument=self._instrument, side=OrderSide.BUY, quantity=Decimal("10"), limit_price=Decimal("101"))
                self.submitted_order = order
                self.submit_order(order, self._broker)


def test_buy_limit_with_two_ask_levels_partial_fill() -> None:
    """Scenario 1: BUY Limit at 101 against asks at 101x5 and 102x5.

    OrderBook asks:
    - Level 2: price=102, volume=5
    - Level 1: price=101, volume=5

    With deterministic on-touch fills, we expect a partial fill of 5 units at 101
    and 5 units remaining unfilled at the Limit price.
    """

    # Arrange: engine + SimBroker (deterministic on-touch fills) + strategy
    engine = TradingEngine()
    # TODO: we should remove this, after we use some default deterministic fill model in SimBroker
    fill_model = DistributionFillModel(limit_on_touch_fill_probability=Decimal("1"), rng_seed=42)
    broker = SimBroker(fill_model=fill_model)
    engine.add_broker("sim_broker", broker)

    # OrderBook snapshot: asks at 101x5 and 102x5; bid at 99x10 to satisfy margin model while focusing on asks
    instrument = TST.instrument.create_equity_aapl()
    order_book = TST.order_book.create_order_book_from_strings(instrument=instrument, bids=["99@10"], asks=["101@5", "102@5"])
    strategy_name = "limit_order_two_levels"
    strategy = SingleLimitOrderOrderBookStrategy(name=strategy_name, broker=broker, instrument=order_book.instrument, order_books=[order_book])
    engine.add_strategy(strategy)

    # Act
    engine.start()

    # Assert: exactly one execution of 5 units at or below limit price
    executions = engine.list_executions_for_strategy(strategy_name)
    assert len(executions) == 1
    total_filled_quantity = sum(Decimal(execution.quantity) for execution in executions)
    assert total_filled_quantity == Decimal("5")

    # Position should be long 5 units on the instrument
    position = broker.get_position(order_book.instrument)
    assert position is not None
    assert position.quantity == Decimal("5")


def test_buy_limit_with_three_ask_levels_rejected_by_price() -> None:
    """Scenario 2: BUY Limit at 101 against asks at 100x3, 101x5 and 102x5.

    OrderBook asks:
    - Level 3: price=102, volume=5
    - Level 2: price=101, volume=5
    - Level 1: price=100, volume=3

    With the current price-eligibility rule (BUY limit must be <= best_ask),
    this order is rejected because $limit_price (101) is above $best_ask (100).
    This test ensures the rejection scenario is easy to reproduce and debug.
    """

    # Arrange: engine + SimBroker (deterministic on-touch fills) + strategy
    engine = TradingEngine()
    # TODO: we should remove this, after we use some default deterministic fill model in SimBroker
    fill_model = DistributionFillModel(limit_on_touch_fill_probability=Decimal("1"), rng_seed=42)
    broker = SimBroker(fill_model=fill_model)
    engine.add_broker("sim_broker", broker)

    # OrderBook snapshot: asks at 100x3, 101x5, 102x5; bid at 99x10 to satisfy margin model while focusing on asks
    instrument = TST.instrument.create_equity_aapl()
    order_book = TST.order_book.create_order_book_from_strings(instrument=instrument, bids=["99@10"], asks=["100@3", "101@5", "102@5"])
    strategy_name = "limit_order_three_levels"
    strategy = SingleLimitOrderOrderBookStrategy(name=strategy_name, broker=broker, instrument=order_book.instrument, order_books=[order_book])
    engine.add_strategy(strategy)

    # Act
    engine.start()

    # Assert: no executions and REJECTED final order state
    executions = engine.list_executions_for_strategy(strategy_name)
    assert len(executions) == 0

    order = strategy.submitted_order
    assert order is not None
    assert order.state == OrderState.REJECTED
