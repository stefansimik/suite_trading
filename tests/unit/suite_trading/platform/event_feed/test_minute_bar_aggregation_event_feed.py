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
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.platform.event_feed.minute_bar_aggregation_event_feed import (
    MinuteBarAggregationEventFeed,
)
from suite_trading.strategy.strategy import Strategy
from suite_trading.utils.data_generation.bar_generation import create_bar_type, create_bar

logger = logging.getLogger(__name__)


class ConfigurableStrategy(Strategy):
    def __init__(
        self,
        *,
        source_feed_1_min,
        emit_first_partial: bool = False,
    ) -> None:
        """Strategy that consumes a provided $source_feed and aggregates to 5-minute bars.

        Tests construct the specific EventFeed (GeneratedBarsEventFeed or FixedSequenceEventFeed)
        and pass it in. This keeps the Strategy simple and avoids ambiguous configuration.

        Args:
            source_feed_1_min: The input EventFeed emitting NewBarEvent(s) with 1-minute bars.
            emit_first_partial: Whether the aggregator should emit the first partial window.
        """
        super().__init__()
        self._count_1min_bars_processed: int = 0
        self._count_5min_bars_processed: int = 0
        self._emit_first_partial = emit_first_partial
        self._source_feed_1_min = source_feed_1_min
        self._agg_end_minutes: list[int] = []

    def on_start(self) -> None:
        # Wire the provided source feed and a 5-minute aggregation feed.
        self.add_event_feed("source_1min", self._source_feed_1_min)
        agg_feed = MinuteBarAggregationEventFeed(
            source_feed=self._source_feed_1_min,
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
                # Record end minute of aggregated 5-minute bar for boundary assertions
                self._agg_end_minutes.append(bar.end_dt.minute)


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
    # Build a GeneratedBarsEventFeed starting at minute 1
    bt_1m = create_bar_type(value=1, unit=BarUnit.MINUTE)
    first_end_dt = datetime(2025, 1, 2, 0, 1, 0, tzinfo=timezone.utc)
    first_bar = create_bar(bar_type=bt_1m, end_dt=first_end_dt)
    src_feed = GeneratedBarsEventFeed(first_bar=first_bar, num_bars=count_1min_bars)
    strategy = ConfigurableStrategy(source_feed_1_min=src_feed)
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
    # Build a GeneratedBarsEventFeed starting at minute 3
    bt_1m = create_bar_type(value=1, unit=BarUnit.MINUTE)
    first_end_dt = datetime(2025, 1, 2, 0, 3, 0, tzinfo=timezone.utc)
    first_bar = create_bar(bar_type=bt_1m, end_dt=first_end_dt)
    src_feed = GeneratedBarsEventFeed(first_bar=first_bar, num_bars=count_1min_bars)
    strategy = ConfigurableStrategy(source_feed_1_min=src_feed, emit_first_partial=emit_first_partial)
    engine.add_strategy("agg_strategy", strategy)

    engine.start()

    assert strategy._count_1min_bars_processed == count_1min_bars
    assert strategy._count_5min_bars_processed == expected_count_5min_bars


@pytest.mark.parametrize(
    "emit_first_partial, expected_count_5min_bars, expected_ends",
    [
        (False, 1, [10]),
        (True, 2, [5, 10]),
    ],
)
def test_minute_bar_aggregation_skips_missing_minute_05(
    emit_first_partial: bool,
    expected_count_5min_bars: int,
    expected_ends: list[int],
) -> None:
    # Create four explicit 1-minute bars with end minutes 03, 04, 06, 07 (minute 05 is missing).
    bt_1m = create_bar_type(value=1, unit=BarUnit.MINUTE)
    base_day = datetime(2025, 1, 2, tzinfo=timezone.utc)
    end_minutes = [3, 4, 6, 7]
    bars = [create_bar(bar_type=bt_1m, end_dt=base_day.replace(hour=0, minute=m, second=0)) for m in end_minutes]

    # Wire up the strategy to consume the explicit sequence via FixedSequenceEventFeed and aggregate
    # to 5-minute windows aligned to UTC day boundaries.
    engine = TradingEngine()
    # Wrap bars into NewBarEvent(s) and feed via FixedSequenceEventFeed
    events = [NewBarEvent(bar=b, dt_received=b.end_dt, is_historical=True) for b in bars]
    src_feed = FixedSequenceEventFeed(events)
    strategy = ConfigurableStrategy(source_feed_1_min=src_feed, emit_first_partial=emit_first_partial)
    engine.add_strategy("agg_strategy", strategy)

    engine.start()

    # We always process the four provided 1-minute bars
    assert strategy._count_1min_bars_processed == 4

    # Aggregated 5-minute bars across :05 and :10 boundaries with a missing minute inside the first
    # window. The first partial is emitted only if emit_first_partial=True.
    assert strategy._count_5min_bars_processed == expected_count_5min_bars

    # Check that aggregated bar end times are aligned and match expectations
    assert strategy._agg_end_minutes == expected_ends
