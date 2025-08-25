import logging

from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.demo_bar_event_feed import DemoBarEventFeed
from suite_trading.platform.event_feed.minute_bar_aggregation_event_feed import (
    MinuteBarAggregationEventFeed,
)
from suite_trading.strategy.strategy import Strategy

logger = logging.getLogger(__name__)


class DemoStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()
        self._bars_processed_1m: int = 0
        self._bars_processed_5m: int = 0

    def on_start(self) -> None:
        # Create a 1-minute demo feed with 20 bars to drive the aggregator
        src_feed = DemoBarEventFeed(num_bars=20)
        self.add_event_feed("demo_1m", src_feed)  # ignore 1m events

        # Aggregate to 5-minute bars
        agg_feed = MinuteBarAggregationEventFeed(source_feed=src_feed, window_minutes=5)
        self.add_event_feed("agg_5m", agg_feed)  # use `on_event`

    def on_event(self, event) -> None:
        # Count only aggregated 5-minute bar events
        if isinstance(event, NewBarEvent):
            self.on_bar(event.bar)
        else:
            logger.debug(f"Received (unhandled) event: {event}")

    def on_bar(self, bar) -> None:
        bt = bar.bar_type
        if bt.unit == BarUnit.MINUTE:
            if int(bt.value) == 1:
                self._bars_processed_1m += 1
            if int(bt.value) == 5:
                self._bars_processed_5m += 1


def test_minute_bar_aggregation_basic():
    engine = TradingEngine()
    strategy = DemoStrategy()
    engine.add_strategy("agg_strategy", strategy)

    # Run the engine; it processes until all feeds are finished
    engine.start()

    # 20 x 1-minute bars => windows ending at :05, :10, :15, :20; first partial is dropped
    # Expected aggregated bars: 3 (00:05 is dropped as first partial window)
    assert strategy._bars_processed_1m == 20
    assert strategy._bars_processed_5m == 4
