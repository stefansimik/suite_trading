import logging
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.platform.event_feed.demo_bar_event_feed import DemoBarEventFeed
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.engine.trading_engine import TradingEngine

logger = logging.getLogger(__name__)


class DemoStrategy(Strategy):
    def on_start(self):
        # Add market data via event-feed
        demo_feed: EventFeed = DemoBarEventFeed()
        self.add_event_feed("demo_feed", demo_feed, self.on_event)

    def on_event(self, event):
        if isinstance(event, NewBarEvent):
            self.on_bar(event.bar, event)
        else:
            logger.debug(f"Received event: {event}")

    def on_bar(self, bar, event: NewBarEvent):
        logger.debug(f"Received bar: {bar}")
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
