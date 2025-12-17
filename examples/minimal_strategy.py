from __future__ import annotations

import logging
from decimal import Decimal

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import BarEvent, wrap_bars_to_events
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.domain.order.orders import MarketOrder
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.strategy.strategy import Strategy
from suite_trading.utils.data_generation.assistant import DGA


logger = logging.getLogger(__name__)


class DemoStrategy(Strategy):
    """Buys on the first bar and sells 5 bars later."""

    def __init__(self, name: str, broker: Broker) -> None:
        super().__init__(name)
        # Configuration
        self._broker = broker
        # Internal state
        self._bar_count = 0

    # Invoked once when the Strategy is started
    def on_start(self) -> None:
        # Create 20 synthetic demo bars
        bars = DGA.bars.create_bar_series(num_bars=20)
        # Create an EventFeed from the bars and add it to the Strategy
        bars_event_feed = FixedSequenceEventFeed(wrap_bars_to_events(bars))
        # Add the EventFeed to this Strategy (these bars drive order simulation)
        self.add_event_feed("bars", bars_event_feed, use_for_simulated_fills=True)

    # Invoked for any Event
    def on_event(self, event: Event) -> None:
        # Dispatch Bars to `on_bar()` function
        if isinstance(event, BarEvent):
            self.on_bar(event.bar)

    # Invoked for each Bar
    def on_bar(self, bar: Bar) -> None:
        # Count bars
        self._bar_count += 1

        # Open position on 1st bar
        if self._bar_count == 1:
            # Create and submit market order (open position)
            order = MarketOrder(instrument=bar.instrument, side=OrderSide.BUY, quantity=Decimal("1"))
            self.submit_order(order, self._broker)
            return

        # Close position on 6th bar
        if self._bar_count == 6:
            # Create and submit market order (close position)
            order = MarketOrder(instrument=bar.instrument, side=OrderSide.SELL, quantity=Decimal("1"))
            self.submit_order(order, self._broker)

    # Invoked once when the Strategy is stopped
    def on_stop(self) -> None:
        logger.info(f"Strategy finished after {self._bar_count} bars")


def run() -> None:
    # Engine is main orchestrator
    engine = TradingEngine()

    # Create broker and add it to engine
    sim_broker = SimBroker()
    engine.add_broker("sim", sim_broker)

    # Create strategy and add it to engine
    strategy = DemoStrategy(name="demo_strategy", broker=sim_broker)
    engine.add_strategy(strategy)

    # Start processing
    engine.start()


if __name__ == "__main__":
    run()
