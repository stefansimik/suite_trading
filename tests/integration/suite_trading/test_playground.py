from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.engine.trading_engine import TradingEngine


class DemoStrategy(Strategy):
    def on_start(self):
        # Strategy started - ready to receive events
        pass

    def on_event(self, event):
        # Handle all events
        pass

    def on_bar(self, bar, is_historical: bool):
        pass


def test_basic_flow():
    # Create a trading engine
    engine: TradingEngine = TradingEngine()

    # Add strategy
    strategy: Strategy = DemoStrategy()
    engine.add_strategy("demo_strategy", strategy)

    # Start trading engine
    engine.start()

    # Stop trading engine
    engine.stop()


if __name__ == "__main__":
    test_basic_flow()
