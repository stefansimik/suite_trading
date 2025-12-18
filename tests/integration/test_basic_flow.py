import logging
from datetime import timedelta
from suite_trading.domain.market_data.bar.bar_event import BarEvent, wrap_bars_to_events
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.platform.event_feed.periodic_time_event_feed import FixedIntervalEventFeed
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.utils.data_generation.assistant import DGA

logger = logging.getLogger(__name__)


class DemoStrategy(Strategy):
    # Standard callback, when strategy starts.
    def on_start(self):
        logger.debug("Strategy starting...")

        # Add data to strategy: 1-minute bar (demo data)
        bars_feed: EventFeed = FixedSequenceEventFeed(wrap_bars_to_events(DGA.bar.create_series(num_bars=20)))
        self.add_event_feed("bars_feed", bars_feed)

        # Add data to strategy: Time notifications each 10 seconds
        time_feed: EventFeed = FixedIntervalEventFeed(
            start_dt=bars_feed.peek().bar.end_dt,  # Align first time notification with first bar
            interval=timedelta(seconds=10),  # Le'ts have time notifications each 10 seconds
            finish_with_feed=bars_feed,  # Stop time notifications, when $bars_feed is finished
        )
        self.add_event_feed("time_feed", time_feed)

    # Standard callback for all events
    def on_event(self, event):
        if isinstance(event, BarEvent):
            self.on_bar(event.bar)  # Dispatch to custom callback
        else:
            # Handle all other events here
            logger.debug(f"Received (unhandled) event: {event}")

    # Custom handler for bar
    def on_bar(self, bar):
        logger.debug(f"Received bar: {bar}")

    # Standard callback, when strategy stops
    def on_stop(self):
        logger.debug("Strategy stopping...")


def test_basic_flow():
    # Create a trading engine
    engine: TradingEngine = TradingEngine()

    # Add strategy
    strategy: Strategy = DemoStrategy(name="demo_strategy")
    engine.add_strategy(strategy)

    # Start trading engine
    engine.start()
