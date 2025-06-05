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
    from decimal import Decimal

    # Create a bar type
    bar_type = create_bar_type(value=5, unit=BarUnit.MINUTE)

    # Create default prices
    open_price = Decimal("1.1000")
    high_price = Decimal("1.1100")
    low_price = Decimal("1.0900")
    close_price = Decimal("1.1050")

    # Create a bar with the bar_type
    bar = create_bar(
        bar_type=bar_type,
        end_dt=datetime.now(timezone.utc),
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
    )
    engine.publish_bar(bar)

    # Stop trading engine
    engine.stop()
