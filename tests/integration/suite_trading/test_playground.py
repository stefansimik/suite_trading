from suite_trading.strategy.base import Strategy
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.utils.data_generation.bars import create_bar_type, create_bar_series, DEFAULT_FIRST_BAR
from datetime import datetime
from typing import Optional, Sequence
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar import Bar


class MockMarketDataProvider:
    """Mock market data provider for testing."""

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    def get_historical_bars_series(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: Optional[datetime] = None,
    ) -> Sequence[Bar]:
        return []

    def stream_historical_bars(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: Optional[datetime] = None,
    ) -> None:
        pass

    def subscribe_to_live_bars(self, bar_type: BarType) -> None:
        pass

    def subscribe_to_live_bars_with_history(
        self,
        bar_type: BarType,
        history_days: int,
    ) -> None:
        pass

    def unsubscribe_from_live_bars(self, bar_type: BarType) -> None:
        pass


class DemoStrategy(Strategy):
    def on_start(self):
        # Using the demo data module to create a bar type
        eurusd_1min_bars_type = create_bar_type(value=1, unit=BarUnit.MINUTE)
        self.subscribe_bars(eurusd_1min_bars_type)

    def on_bar(self, bar, is_historical: bool):
        pass


def test_basic_flow():
    # Create a trading engine
    engine: TradingEngine = TradingEngine()

    # Set mock market data provider
    mock_provider = MockMarketDataProvider()
    engine.set_market_data_provider(mock_provider)

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
