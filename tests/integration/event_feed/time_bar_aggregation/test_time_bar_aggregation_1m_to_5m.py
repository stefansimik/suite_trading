import logging
from datetime import datetime, timezone
from typing import Iterable

import pytest

from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.bar.bar_event import BarEvent, wrap_bars_to_events
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.fixed_sequence_event_feed import (
    FixedSequenceEventFeed,
)
from suite_trading.platform.event_feed.time_bar_aggregation_event_feed import (
    TimeBarAggregationEventFeed,
)
from suite_trading.strategy.strategy import Strategy
from tests.helpers.test_assistant import TEST_ASSISTANT as TST

logger = logging.getLogger(__name__)


class TestStrategy(Strategy):
    """Strategy wiring a 1‑minute source feed to a 5‑minute aggregator (defaults).

    Records counts and end timestamps of emitted 5‑minute bars for assertions.
    """

    def __init__(self, *, name: str, source_feed_1_min) -> None:
        super().__init__(name)
        # Input params
        self._source_feed_1_min = source_feed_1_min

        # Local state
        self.count_1m: int = 0
        self.count_5m: int = 0
        self.ends_5m: list[datetime] = []

    def on_start(self) -> None:
        # 1-min feed
        self.add_event_feed("source_1m", self._source_feed_1_min)
        # 5-min feed
        agg = TimeBarAggregationEventFeed(source_feed=self._source_feed_1_min, unit=BarUnit.MINUTE, size=5)
        self.add_event_feed("agg_5m", agg)

    def on_event(self, event) -> None:
        if not isinstance(event, BarEvent):
            logger.debug(f"Received non-bar event (ignored): {event}")
            return

        bar = event.bar
        bt = bar.bar_type
        if bt.unit == BarUnit.MINUTE:
            if int(bt.value) == 1:
                self.count_1m += 1
            elif int(bt.value) == 5:
                self.count_5m += 1
                self.ends_5m.append(bar.end_dt)


def build_feed_from_minute_ends(
    *,
    base_day: datetime,
    end_minutes: Iterable[int],
    unit_minutes: int = 1,
) -> FixedSequenceEventFeed:
    """Build a FixedSequenceEventFeed from explicit minute-end integers (UTC hour 00).

    Args:
        base_day: UTC date used to anchor generated bar timestamps (hour=00 is used).
        end_minutes: Minute ends to create bars for (e.g., [1, 2, 3, 4, 5]).
        unit_minutes: Bar unit size in minutes (1 for input series).

    Returns:
        FixedSequenceEventFeed of BarEvent(s) in the exact provided order.
    """
    bt = TST.bars.create_bar_type(value=unit_minutes, unit=BarUnit.MINUTE)
    bars = [
        TST.bars.create_bar(
            bar_type=bt,
            end_dt=base_day.replace(hour=0, minute=m, second=0, microsecond=0),
        )
        for m in end_minutes
    ]
    return FixedSequenceEventFeed(wrap_bars_to_events(bars))


@pytest.mark.parametrize(
    "input_1min_bars, expected_ends_5m",
    [
        # ALIGNED
        ([1, 2, 3, 4, 5], [5]),
        ([1, 2, 3, 4], []),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [5, 10]),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], [5, 10, 15, 20]),
        ([1, 2, 3, 4, 6], [5]),
        ([1, 1, 2, 3, 4, 5], [5]),
        # MISALIGNED STARTS
        ([3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20], [5, 10, 15, 20]),
        # GAPS
        ([3, 4, 6, 7, 11], [5, 10]),
        ([1, 2, 3, 4, 5, 6, 8, 9, 10], [5, 10]),
        # JUMPS
        ([4, 12], [5]),
        ([2, 29, 47], [5, 30]),
        # SPARSE / BOUNDARY-ONLY
        ([5], [5]),
        ([1, 5], [5]),
        # EDGE CASES
        ([], []),
        ([0, 1, 2, 3, 4], [0]),
        ([0], [0]),
    ],
)
def test_1m_to_5m_emits_end_minutes(
    input_1min_bars,
    expected_ends_5m,
):
    """Single parametrized test for 1‑min → 5‑min aggregation under default policies.

    Inputs are minute ends within a single UTC hour (:00). Aggregator uses defaults
    (emit_first_partial_bar=True, emit_later_partial_bars=True).
    """
    engine = TradingEngine()
    base_day = datetime(2025, 1, 2, tzinfo=timezone.utc)
    event_feed_1min_bars = build_feed_from_minute_ends(base_day=base_day, end_minutes=input_1min_bars)

    strategy = TestStrategy(name="test_strategy", source_feed_1_min=event_feed_1min_bars)
    engine.add_strategy(strategy)

    engine.start()

    # Assert input count matches processed 1‑minute bars
    assert strategy.count_1m == len(input_1min_bars)

    # Assert exact aggregated 5‑minute bar end minutes
    got_ends = [dt.minute for dt in strategy.ends_5m]
    assert got_ends == expected_ends_5m

    # Assert count matches expectations
    assert strategy.count_5m == len(expected_ends_5m)
