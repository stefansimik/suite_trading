from suite_trading import Strategy, TradingEngine
from suite_trading.domain.market_data.bar import BarUnit
from suite_trading.utils.data_generation.bars import create_bar_type, create_bar


class DemoStrategy(Strategy):
    def on_start(self):
        # Using the demo data module to create a bar type
        eurusd_1min_bars_type = create_bar_type(value=5, unit=BarUnit.MINUTE)
        self.subscribe_bars(eurusd_1min_bars_type)


def test_basic_flow():
    # Create a trading engine
    engine: TradingEngine = TradingEngine()

    # Create + add strategy
    strategy: Strategy = DemoStrategy("DemoStrategy01")
    engine.add_strategy(strategy)

    # Start trading engine
    engine.start()

    # Publish bar
    from datetime import datetime, timezone

    # Create a bar type
    bar_type = create_bar_type(value=5, unit=BarUnit.MINUTE)

    # Create a bar using default implementation with a fixed datetime
    bar = create_bar(
        bar_type=bar_type,
        end_dt=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    engine.publish_bar(bar)

    # Stop trading engine
    engine.stop()
