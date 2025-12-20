from __future__ import annotations

import logging
from decimal import Decimal

from suite_trading.domain.order.order_fill import OrderFill
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.domain.market_data.bar.bar_event import BarEvent, wrap_bars_to_events
from suite_trading.domain.order.orders import MarketOrder, Order
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.utils.data_generation.assistant import DGA


logger = logging.getLogger(__name__)


def _create_optimistic_sim_broker() -> SimBroker:
    fill_model = DistributionFillModel(market_fill_adjustment_distribution={0: Decimal("1")}, limit_on_touch_fill_probability=Decimal("1"), rng_seed=42)
    return SimBroker(fill_model=fill_model)


class TwoTradeDemoStrategy(Strategy):
    """Trivial demo strategy for Plan Step 1.

    Behavior:
    - Adds a FixedSequenceEventFeed of 10 rising bar (Step 0)
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
        # Step 0: generate 10 rising bar and wrap into BarEvent(s)
        bars = DGA.bar.create_series(num_bars=10)
        prices_feed = FixedSequenceEventFeed(wrap_bars_to_events(bars))
        self.add_event_feed(self._prices_feed_name, prices_feed, use_for_simulated_fills=True)

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

    def on_order_fill(self, order_fill: OrderFill) -> None:
        pass

    def on_order_state_update(self, order: Order) -> None:
        pass

    @property
    def processed_event_count(self) -> int:
        return self._event_count


def test_two_trade_demo_strategy_steps_0_and_1():
    # Arrange: engine + SimBroker + strategy
    engine = TradingEngine()
    broker = _create_optimistic_sim_broker()
    engine.add_broker("sim_broker", broker)

    strategy = TwoTradeDemoStrategy(name="two_trade_demo_strategy", broker=broker)
    engine.add_strategy(strategy)

    # Act
    engine.start()

    # Assert: exactly two submissions resulted in order fills (SELL then BUY)
    # Note: broker.list_active_orders() will be empty because orders are filled (terminal)
    active = broker.list_active_orders()
    assert len(active) == 0, "All orders should be terminal and cleaned up"

    # The Strategy should have processed at least 5 events and then stopped (feed closed)
    assert strategy.processed_event_count == 5

    # Verify order fills were tracked by TradingEngine
    order_fills = engine.list_order_fills_for_strategy("two_trade_demo_strategy")
    assert len(order_fills) == 2, "Engine should track exactly two order fills"

    # First order_fill: SELL
    assert order_fills[0].order.side == OrderSide.SELL
    assert order_fills[0].quantity == Decimal("1")

    # Second order_fill: BUY
    assert order_fills[1].order.side == OrderSide.BUY
    assert order_fills[1].quantity == Decimal("1")
