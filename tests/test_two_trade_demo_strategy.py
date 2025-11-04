from __future__ import annotations

import logging
from decimal import Decimal

from suite_trading.domain.order.execution import Execution
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.domain.market_data.bar.bar_event import BarEvent, wrap_bars_to_events
from suite_trading.utils.data_generation.bar_generation import create_bar_series
from suite_trading.domain.order.orders import MarketOrder, Order
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.broker.sim.sim_broker import SimBroker


logger = logging.getLogger(__name__)


class TwoTradeDemoStrategy(Strategy):
    """Trivial demo strategy for Plan Step 1.

    Behavior:
    - Adds a FixedSequenceEventFeed of 10 rising bars (Step 0)
    - Counts incoming BarEvent(s) as "price events"
    - On 3rd event: submit SELL Market order qty=1
    - On 5th event: submit BUY Market order qty=1, then stop by closing the feed
    """

    def __init__(self, name: str, broker: Broker) -> None:
        super().__init__(name)
        self._broker = broker
        self._event_count: int = 0
        self._prices_feed_name = "prices_feed"

    def on_start(self) -> None:
        logger.info(f"Started Strategy named '{self.name}'")
        # Step 0: generate 10 rising bars and wrap into BarEvent(s)
        bars = create_bar_series(num_bars=10)
        prices_feed = FixedSequenceEventFeed(wrap_bars_to_events(bars))
        self.add_event_feed(self._prices_feed_name, prices_feed)

    def on_event(self, event) -> None:
        if isinstance(event, BarEvent):
            self._event_count += 1
            bar = event.bar
            # Use the Broker instance provided at construction
            broker = self._broker

            if self._event_count == 3:
                order = MarketOrder(instrument=bar.instrument, side=OrderSide.SELL, quantity=Decimal("1"))
                self.submit_order(order, broker)
                logger.info(f"Submitted SELL Market order on event #{self._event_count}")

            if self._event_count == 5:
                order = MarketOrder(instrument=bar.instrument, side=OrderSide.BUY, quantity=Decimal("1"))
                self.submit_order(order, broker)
                logger.info(f"Submitted BUY Market order on event #{self._event_count}")
                # Request strategy stop by closing feed (engine will auto-stop it)
                self.remove_event_feed(self._prices_feed_name)

    def on_execution(self, execution: Execution) -> None:
        pass

    def on_order_updated(self, order: Order) -> None:
        pass

    @property
    def processed_event_count(self) -> int:
        return self._event_count


def test_two_trade_demo_strategy_steps_0_and_1():
    # Arrange: engine + SimBroker + strategy
    engine = TradingEngine()
    broker = SimBroker()
    engine.add_broker("sim_broker", broker)

    strategy = TwoTradeDemoStrategy(name="two_trade_demo_strategy", broker=broker)
    engine.add_strategy(strategy)

    # Act
    engine.start()

    # Assert: exactly two submissions on events 3 and 5 with SELL then BUY
    submitted = broker.list_orders()
    assert len(submitted) == 2, "Strategy should submit exactly two orders"
    assert submitted[0].side == OrderSide.SELL
    assert submitted[1].side == OrderSide.BUY

    # The Strategy should have processed at least 5 events and then stopped (feed closed)
    assert strategy.processed_event_count == 5

    # Verify executions were tracked by TradingEngine
    executions = engine.list_executions_for_strategy("two_trade_demo_strategy")
    assert len(executions) == 2, "Engine should track exactly two executions"

    # First execution: SELL
    assert executions[0].order.side == OrderSide.SELL
    assert executions[0].quantity == Decimal("1")

    # Second execution: BUY
    assert executions[1].order.side == OrderSide.BUY
    assert executions[1].quantity == Decimal("1")
