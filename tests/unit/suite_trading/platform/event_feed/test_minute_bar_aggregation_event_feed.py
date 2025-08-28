"""Tests for MinuteBarAggregationEventFeed aggregation behavior.

Logical structure:
- We generate 1-minute bars using GeneratedBarsEventFeed. The starting minute (end time minute)
  of the first 1-minute bar is configurable.
- We aggregate those 1-minute bars into 5-minute bars aligned to day boundaries (ends at
  minutes 5, 10, 15, ...). The aggregator can optionally emit the first partial window via
  the emit_first_partial flag.
- The Strategy subscribes to both the source 1-minute feed and the aggregated 5-minute
  feed, and counts observed NewBarEvent(s) by bar unit and value. This allows us to assert
  both the total number of 1-minute bars consumed and the number of aggregated 5-minute
  bars produced.

Scenarios covered:
- First bar end minute = 1
  - 20 x 1-min -> 4 x 5-min (emit_first_partial = False)
  - 19 x 1-min -> 3 x 5-min (emit_first_partial = False)
  - 21 x 1-min -> 4 x 5-min (emit_first_partial = False)
- First bar end minute = 3
  - 20 x 1-min -> 3 x 5-min (emit_first_partial = False)
  - 20 x 1-min -> 3 x 5-min (emit_first_partial = True)
"""

import logging
from datetime import datetime, timezone

import pytest

from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.generated_bars_event_feed import GeneratedBarsEventFeed
from suite_trading.platform.event_feed.minute_bar_aggregation_event_feed import (
    MinuteBarAggregationEventFeed,
)
from suite_trading.strategy.strategy import Strategy
from suite_trading.utils.data_generation.bars import create_bar_type, create_bar

logger = logging.getLogger(__name__)


class ConfigurableStrategy(Strategy):
    def __init__(
        self,
        *,
        count_1min_bars: int,
        first_bar_end_minute: int,
        emit_first_partial: bool = False,
    ) -> None:
        super().__init__()
        self._count_1min_bars_processed: int = 0
        self._count_5min_bars_processed: int = 0
        self._count_1min_bars = count_1min_bars
        self._first_bar_end_minute = first_bar_end_minute
        self._emit_first_partial = emit_first_partial

    def on_start(self) -> None:
        # Build a 1-minute first bar with a specific end minute (UTC day 2025-01-02)
        bt_1m = create_bar_type(value=1, unit=BarUnit.MINUTE)
        first_end_dt = datetime(2025, 1, 2, 0, self._first_bar_end_minute, 0, tzinfo=timezone.utc)
        first_bar = create_bar(bar_type=bt_1m, end_dt=first_end_dt)

        # Create the 1-minute demo feed with the configured number of bars
        src_feed = GeneratedBarsEventFeed(first_bar=first_bar, num_bars=self._count_1min_bars)
        self.add_event_feed("source_1min", src_feed)  # source 1-min feed (we still count its events)

        # Aggregate to 5-minute bars
        agg_feed = MinuteBarAggregationEventFeed(
            source_feed=src_feed,
            window_minutes=5,
            emit_first_partial=self._emit_first_partial,
        )
        self.add_event_feed("agg_5min", agg_feed)

    def on_event(self, event) -> None:
        if isinstance(event, NewBarEvent):
            self.on_bar(event.bar)
        else:
            logger.debug(f"Received (unhandled) event: {event}")

    def on_bar(self, bar) -> None:
        bt = bar.bar_type
        if bt.unit == BarUnit.MINUTE:
            if int(bt.value) == 1:
                self._count_1min_bars_processed += 1
            if int(bt.value) == 5:
                self._count_5min_bars_processed += 1


@pytest.mark.parametrize(
    "count_1min_bars, expected_count_5min_bars",
    [
        (20, 4),  # 20x 1-min -> 4x 5-min
        (19, 3),  # 19x 1-min -> 3x 5-min
        (21, 4),  # 21x 1-min -> 4x 5-min
    ],
)
def test_minute_bar_aggregation_first_minute_is_1(count_1min_bars, expected_count_5min_bars: int):
    engine = TradingEngine()
    strategy = ConfigurableStrategy(count_1min_bars=count_1min_bars, first_bar_end_minute=1)
    engine.add_strategy("agg_strategy", strategy)

    engine.start()

    assert strategy._count_1min_bars_processed == count_1min_bars
    assert strategy._count_5min_bars_processed == expected_count_5min_bars


@pytest.mark.parametrize(
    "emit_first_partial, count_1min_bars, expected_count_5min_bars",
    [
        (False, 20, 3),
        (True, 20, 4),
    ],
)
def test_minute_bar_aggregation_first_minute_is_3_emit_first_partial_cases(emit_first_partial: bool, count_1min_bars: int, expected_count_5min_bars: int):
    engine = TradingEngine()
    strategy = ConfigurableStrategy(
        count_1min_bars=count_1min_bars,
        first_bar_end_minute=3,
        emit_first_partial=emit_first_partial,
    )
    engine.add_strategy("agg_strategy", strategy)

    engine.start()

    assert strategy._count_1min_bars_processed == count_1min_bars
    assert strategy._count_5min_bars_processed == expected_count_5min_bars
