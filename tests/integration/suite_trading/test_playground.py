from suite_trading import Strategy, TradingEngine
from suite_trading.domain.market_data.bar import BarUnit
from suite_trading.utils.data_generation import create_bar_type, create_bar_series, DEFAULT_FIRST_BAR


class DemoStrategy(Strategy):
    def on_start(self):
        # Using the demo data module to create a bar type
        eurusd_1min_bars_type = create_bar_type(value=5, unit=BarUnit.MINUTE)
        self.subscribe_bars(eurusd_1min_bars_type)


def test_basic_flow():
    # Create a trading engine
    engine: TradingEngine = TradingEngine()

    # Add strategy
    strategy: Strategy = DemoStrategy("DemoStrategy01")
    engine.add_strategy(strategy)

    # Start trading engine
    engine.start()

    # Feed bars to the engine
    bars = create_bar_series(first_bar=DEFAULT_FIRST_BAR, num_bars=20)
    for bar in bars:
        engine.publish_bar(bar)

    # Stop trading engine
    engine.stop()


if __name__ == "__main__":
    test_basic_flow()
