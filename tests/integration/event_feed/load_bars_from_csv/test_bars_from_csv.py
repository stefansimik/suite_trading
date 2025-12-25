import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from suite_trading.domain.instrument import Instrument, AssetClass
from suite_trading.domain.monetary.currency_registry import USD
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.market_data.bar.bar_event import BarEvent
from suite_trading.platform.event_feed.bars_from_dataframe_event_feed import BarsFromDataFrameEventFeed
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.strategy.strategy import Strategy

logger = logging.getLogger(__name__)

# CSV file used in this test module (kept for documentation only)
CSV_FILE_NAME = "demo_bars.csv"
CSV_PATH = Path(__file__).with_name(CSV_FILE_NAME)

# Describe BarType for bars constructed in the CSV (or equivalent) data
INSTRUMENT = Instrument(
    name="EURUSD",
    exchange="FOREX",
    asset_class=AssetClass.FX_SPOT,
    price_increment="0.00001",
    qty_increment="1",
    contract_size="100000",
    contract_unit="EUR",
    quote_currency=USD,
)
BAR_TYPE = BarType(INSTRUMENT, 1, BarUnit.MINUTE, PriceType.LAST_TRADE)


def _create_demo_bars_dataframe() -> pd.DataFrame:
    """Create a small in-memory DataFrame with demo bars.

    The original test loaded bars from `demo_bars.csv`. That file is no longer
    present in the repository, so we construct an equivalent DataFrame in
    memory instead. This keeps the test focused on verifying that
    `BarsFromDataFrameEventFeed` can stream bars from a DataFrame while making
    the test self-contained.
    """
    num_bars = 10
    minutes = [i for i in range(num_bars)]
    start_dts = [datetime(2025, 1, 1, 9, 0, 0, tzinfo=timezone.utc) + pd.Timedelta(minutes=m) for m in minutes]
    end_dts = [dt + pd.Timedelta(minutes=1) for dt in start_dts]

    # Simple rising price pattern for clarity
    opens = [1.10 + 0.001 * i for i in minutes]
    highs = [o + 0.0005 for o in opens]
    lows = [o - 0.0005 for o in opens]
    closes = [o + 0.0002 for o in opens]
    volumes = [100_000 for _ in minutes]

    df = pd.DataFrame(
        {
            "start_dt": start_dts,
            "end_dt": end_dts,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        },
    )
    return df


class DemoStrategy(Strategy):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._bars_processed: int = 0

    # Standard callback, when strategy starts.
    def on_start(self):
        logger.debug("Strategy starting...")

        # FEED STRATEGY FROM BARS LOADED FROM A DEMO DATAFRAME

        # Step 1: Build DataFrame with bar-data (replaces CSV on disk)
        df = _create_demo_bars_dataframe()

        # Step 2: Use declared BAR_TYPE for loaded bars

        # Step 3: Create EventFeed, that generates bars and feeds them to the strategy
        bars_feed: EventFeed = BarsFromDataFrameEventFeed(df=df, bar_type=BAR_TYPE)
        self.add_event_feed("bars_from_csv_feed", bars_feed)

    # Standard callback for all events
    def on_event(self, event):
        if isinstance(event, BarEvent):
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
    strategy: Strategy = DemoStrategy(name="bars_from_csv_strategy")
    engine.add_strategy(strategy)

    # Start trading engine (should process exactly the bars in the demo DataFrame)
    engine.start()

    # Assertions
    assert isinstance(strategy, DemoStrategy)

    # Calculate expected number of bars from the same demo DataFrame used by the strategy
    expected_bars = len(_create_demo_bars_dataframe())

    assert strategy.bars_processed == expected_bars
