import logging
from datetime import datetime, timezone, timedelta
from typing import Iterable, NamedTuple

import pytest

from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent, wrap_bars_to_events
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.fixed_sequence_event_feed import (
    FixedSequenceEventFeed,
)
from suite_trading.platform.event_feed.intraday_bar_aggregation_event_feed import (
    IntradayBarAggregationEventFeed,
)
from suite_trading.strategy.strategy import Strategy
from suite_trading.utils.data_generation.bar_generation import (
    create_bar_type,
    create_bar,
)

logger = logging.getLogger(__name__)


# region Helpers


class Period(NamedTuple):
    unit: BarUnit
    size: int


def build_feed_from_end_times(
    *,
    unit: BarUnit,
    size: int,
    end_times: Iterable[datetime],
) -> FixedSequenceEventFeed:
    """Create a FixedSequenceEventFeed from explicit bar end datetimes.

    Args:
        unit: Unit of the source bars (SECOND/MINUTE/HOUR).
        size: Size of the source bars (e.g., 1, 5, 15, 30, 60).
        end_times: Exact end datetimes for the bars in the given order.

    Returns:
        FixedSequenceEventFeed producing NewBarEvent(s) in the provided order.
    """
    bt = create_bar_type(value=size, unit=unit)
    bars = [create_bar(bar_type=bt, end_dt=dt) for dt in end_times]
    return FixedSequenceEventFeed(wrap_bars_to_events(bars))


def boundary_dt_for_target(
    *,
    base_day: datetime,
    unit: BarUnit,
    size: int,
) -> datetime:
    """Return the first boundary end datetime after 00:00 for a given target period.

    For tests we choose the first natural boundary inside the same UTC day:
    - SECOND: 00:00:<size>
    - MINUTE: 00:<size>:00
    - HOUR:   <size>:00:00
    """
    if unit == BarUnit.SECOND:
        return base_day.replace(hour=0, minute=0, second=size, microsecond=0)
    if unit == BarUnit.MINUTE:
        return base_day.replace(hour=0, minute=size, second=0, microsecond=0)
    if unit == BarUnit.HOUR:
        return base_day.replace(hour=size, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported $unit '{unit}' in `boundary_dt_for_target`")


# endregion


# region Strategy


class TestStrategy(Strategy):
    """Strategy wiring a source feed to a IntradayBarAggregationEventFeed.

    Records only aggregated NewBarEvent(s) matching the target period.
    """

    def __init__(
        self,
        *,
        source_feed,
        target: Period,
    ) -> None:
        super().__init__()
        self._source_feed = source_feed
        self._target = target

        # Local state
        self.count_input: int = 0
        self.count_agg: int = 0
        self.ends_agg: list[datetime] = []
        self.types_agg: list[Period] = []

    def on_start(self) -> None:
        # Source event-feed: emits input bars for the Strategy
        self.add_event_feed("source", self._source_feed)

        # Aggregation event-feed: resamples bars from the source feed into the target period
        agg = IntradayBarAggregationEventFeed(
            source_feed=self._source_feed,
            unit=self._target.unit,
            size=self._target.size,
        )
        self.add_event_feed("agg", agg)

    def on_event(self, event) -> None:
        if not isinstance(event, NewBarEvent):
            logger.debug(f"Received non-bar event (ignored): {event}")
            return

        bar = event.bar
        bt = bar.bar_type

        # Count input source bars by excluding aggregated ones via target match.
        if bt.unit == self._target.unit and int(bt.value) == int(self._target.size):
            self.count_agg += 1
            self.ends_agg.append(bar.end_dt)
            self.types_agg.append(Period(bt.unit, int(bt.value)))
        else:
            self.count_input += 1


# endregion


# region Parameters

BASE_1S = Period(BarUnit.SECOND, 1)
BASE_5S = Period(BarUnit.SECOND, 5)
BASE_1M = Period(BarUnit.MINUTE, 1)
BASE_5M = Period(BarUnit.MINUTE, 5)
BASE_15M = Period(BarUnit.MINUTE, 15)
BASE_30M = Period(BarUnit.MINUTE, 30)
BASE_1H = Period(BarUnit.HOUR, 1)

# T_* constants: 'T_' means target period. Pattern: T_<size><unit>; unit is S, MIN, or H
T_5S = Period(BarUnit.SECOND, 5)
T_15S = Period(BarUnit.SECOND, 15)
T_30S = Period(BarUnit.SECOND, 30)
T_1MIN = Period(BarUnit.MINUTE, 1)
T_5MIN = Period(BarUnit.MINUTE, 5)
T_15MIN = Period(BarUnit.MINUTE, 15)
T_20MIN = Period(BarUnit.MINUTE, 20)
T_30MIN = Period(BarUnit.MINUTE, 30)
T_1H = Period(BarUnit.HOUR, 1)
T_2H = Period(BarUnit.HOUR, 2)
T_4H = Period(BarUnit.HOUR, 4)
T_6H = Period(BarUnit.HOUR, 6)
T_12H = Period(BarUnit.HOUR, 12)

MATRIX: dict[Period, list[Period]] = {
    BASE_1S: [T_5S, T_30S, T_1MIN, T_5MIN, T_15MIN, T_30MIN, T_1H, T_2H, T_4H, T_6H, T_12H],
    BASE_5S: [T_15S, T_30S, T_1MIN, T_5MIN, T_15MIN, T_30MIN, T_1H, T_2H, T_4H, T_6H, T_12H],
    BASE_1M: [T_5MIN, T_15MIN, T_20MIN, T_30MIN, T_1H, T_2H, T_4H, T_6H, T_12H],
    BASE_5M: [T_15MIN, T_30MIN, T_1H, T_2H, T_4H, T_6H, T_12H],
    BASE_15M: [T_30MIN, T_1H, T_2H, T_4H, T_6H, T_12H],
    BASE_30M: [T_1H, T_2H, T_4H, T_6H, T_12H],
    BASE_1H: [T_2H, T_4H, T_6H, T_12H],
}

PARAMS = []
for base_period, target_periods in MATRIX.items():
    for target_period in target_periods:
        PARAMS.append(pytest.param(base_period, target_period))

IDS = [f"{p.values[0].size}{p.values[0].unit.name[0]} -> {p.values[1].size}{p.values[1].unit.name[0]}" for p in PARAMS]

pass

# endregion


@pytest.mark.parametrize("base_period, target", PARAMS, ids=IDS)
def test_time_bar_aggregation_single_boundary_emits_and_type_is_correct(
    base_period: Period,
    target: Period,
):
    """Matrix test: one base_period bar at the boundary must emit one aggregated bar.

    The test feeds exactly one base_period bar whose $end_dt equals the first natural boundary of the
    $target period inside the UTC day. According to existing behavior (see 1m→5m tests), an
    event exactly at the boundary emits that aggregated bar immediately.

    Asserts:
    - Aggregated count is 1
    - Aggregated end datetime equals the chosen boundary
    - Aggregated BarType (unit, size) matches $target
    """
    engine = TradingEngine()
    base_day = datetime(2025, 1, 2, tzinfo=timezone.utc)
    boundary = boundary_dt_for_target(
        base_day=base_day,
        unit=target.unit,
        size=target.size,
    )

    feed = build_feed_from_end_times(
        unit=base_period.unit,
        size=base_period.size,
        end_times=[boundary],
    )

    strategy = TestStrategy(source_feed=feed, target=target)
    engine.add_strategy("probe", strategy)

    engine.start()

    # Count of source bars equals 1 (the only event we fed)
    assert strategy.count_input == 1

    # Aggregated output: exactly one bar at the boundary with correct type
    assert strategy.count_agg == 1
    assert strategy.ends_agg == [boundary]
    assert strategy.types_agg == [target]


@pytest.mark.parametrize("base_period, target", PARAMS, ids=IDS)
def test_time_bar_aggregation_spans_five_intervals_with_many_inputs(
    base_period: Period,
    target: Period,
) -> None:
    """Emit many source bars spanning five full aggregated intervals.

    We generate two source bars per target interval: one early bar within the
    interval and one exactly at the boundary. This keeps the test fast (10 input
    bars total) while still verifying aggregation across a longer time range.

    Asserts:
    - Input source event count equals 10 (2 per interval over 5 intervals)
    - Aggregated output count equals 5 (one per target boundary)
    - Aggregated end datetimes equal the five successive boundaries
    - Aggregated BarType (unit, size) matches $target for every emitted bar
    """
    engine = TradingEngine()
    base_day = datetime(2025, 1, 2, tzinfo=timezone.utc)

    # Compute the first target boundary inside the day and time deltas for math
    first_boundary = boundary_dt_for_target(
        base_day=base_day,
        unit=target.unit,
        size=target.size,
    )

    def to_timedelta(p: Period) -> timedelta:
        if p.unit == BarUnit.SECOND:
            return timedelta(seconds=p.size)
        if p.unit == BarUnit.MINUTE:
            return timedelta(minutes=p.size)
        if p.unit == BarUnit.HOUR:
            return timedelta(hours=p.size)
        raise ValueError(f"Unsupported $unit '{p.unit}' in `to_timedelta`")

    target_dt = to_timedelta(target)
    base_dt = to_timedelta(base_period)

    # Build end-times covering 5 target intervals with two source bars per interval
    # Order per interval: an early bar strictly inside the interval, then the boundary bar
    end_times: list[datetime] = []
    boundaries: list[datetime] = []
    for i in range(1, 6):
        boundary_i = first_boundary + (i - 1) * target_dt
        start_i = boundary_i - target_dt
        mid_i = start_i + base_dt  # first base bar end strictly within the interval
        end_times.extend([mid_i, boundary_i])
        boundaries.append(boundary_i)

    feed = build_feed_from_end_times(
        unit=base_period.unit,
        size=base_period.size,
        end_times=end_times,
    )

    strategy = TestStrategy(source_feed=feed, target=target)
    engine.add_strategy("test_strategy", strategy)

    engine.start()

    # Input count: all source bars (none of them match the target type)
    assert strategy.count_input == len(end_times)

    # Aggregated output: exactly one bar per interval at each boundary with correct type
    assert strategy.count_agg == len(boundaries)
    assert strategy.ends_agg == boundaries
    assert strategy.types_agg == [target] * len(boundaries)
