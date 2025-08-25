import logging
from pathlib import Path

import pandas as pd

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.platform.event_feed.bars_from_dataframe_event_feed import BarsFromDataFrameEventFeed
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.strategy.strategy import Strategy

logger = logging.getLogger(__name__)

# CSV file used in this test module
CSV_FILE_NAME = "demo_bars.csv"
CSV_PATH = Path(__file__).with_name(CSV_FILE_NAME)

# Describe BarType for bars constructed in the CSV file
INSTRUMENT = Instrument("EURUSD", "FOREX", 0.00001, 1)
BAR_TYPE = BarType(INSTRUMENT, 1, BarUnit.MINUTE, PriceType.LAST)


class DemoStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()
        self._bars_processed: int = 0

    # Standard callback, when strategy starts.
    def on_start(self):
        logger.debug("Strategy starting...")

        # FEED STRATEGY FROM BARS LOADED FROM CSV FILE

        # Step 1: Load DataFrame from CSV file, which contains bar-data
        df = pd.read_csv(CSV_PATH, parse_dates=["start_dt", "end_dt"])

        # Step 2: Use declared BAR_TYPE for loaded bars

        # Step 3: Create EventFeed, that generates bars and feeds them to the strategy
        bars_feed: EventFeed = BarsFromDataFrameEventFeed(df=df, bar_type=BAR_TYPE)
        self.add_event_feed("bars_from_csv_feed", bars_feed)

    # Standard callback for all events
    def on_event(self, event):
        if isinstance(event, NewBarEvent):
            self._bars_processed += 1
            logger.debug(f"Processed bar #{self._bars_processed}: {event.bar}")
        else:
            logger.debug(f"Received (unhandled) event: {event}")

    # Standard callback, when strategy stops
    def on_stop(self):
        logger.debug("Strategy stopping...")

    # Helper for assertions
    @property
    def bars_processed(self) -> int:
        return self._bars_processed


def test_dataframe_feed_demo():
    # Create a trading engine
    engine: TradingEngine = TradingEngine()

    # Add strategy that uses only BarsFromDataFrameEventFeed
    strategy: Strategy = DemoStrategy()
    engine.add_strategy("bars_from_csv_strategy", strategy)

    # Start trading engine (should process exactly 10 bars from CSV)
    engine.start()

    # Assertions
    assert isinstance(strategy, DemoStrategy)

    # Calculate expected number of bars from the same CSV used by the strategy
    expected_bars = len(pd.read_csv(CSV_PATH, parse_dates=["start_dt", "end_dt"]))

    assert strategy.bars_processed == expected_bars
