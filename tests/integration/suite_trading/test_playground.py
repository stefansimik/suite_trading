import logging
from datetime import timedelta
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.platform.event_feed.demo_bar_event_feed import DemoBarEventFeed
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.platform.event_feed.periodic_time_event_feed import PeriodicTimeEventFeed, TimeTickEvent
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.engine.trading_engine import TradingEngine

logger = logging.getLogger(__name__)


class DemoStrategy(Strategy):
    def __init__(self):
        super().__init__()
        self.bars_feed = None
        self.time_feed = None

    def on_start(self):
        # Add market data via event-feed
        bars_feed: EventFeed = DemoBarEventFeed(num_bars=20)
        self.add_event_feed("bars_feed", bars_feed, self.on_event)
        self.bars_feed = bars_feed  # Remember feed

        # Add a periodic time event-feed aligned with bar feed timeline
        start_dt_of_demo_bar_event_feed = bars_feed.peek().bar.end_dt
        time_feed: EventFeed = PeriodicTimeEventFeed(
            start_datetime=start_dt_of_demo_bar_event_feed,
            interval=timedelta(seconds=10),
            end_datetime=start_dt_of_demo_bar_event_feed + timedelta(minutes=20),
            finish_with_feed=bars_feed,
        )
        self.add_event_feed("time_feed", time_feed, self.on_event)
        self.time_feed = time_feed  # Remember feed

    def on_event(self, event):
        if isinstance(event, NewBarEvent):
            self.on_bar(event.bar, event)
        elif isinstance(event, TimeTickEvent):
            logger.debug(f"Received time tick: {event}")
        else:
            logger.debug(f"Received event: {event}")

    def on_bar(self, bar, event: NewBarEvent):
        logger.debug(f"Received bar: {bar}")
        # Time-feed will auto-finish when bars-feed finishes via $finish_with_feed.
        pass

    def on_stop(self):
        pass


def test_basic_flow():
    # Create a trading engine
    engine: TradingEngine = TradingEngine()

    # Add strategy
    strategy: Strategy = DemoStrategy()
    engine.add_strategy("demo_strategy", strategy)

    # Start trading engine
    engine.start()


if __name__ == "__main__":
    test_basic_flow()
