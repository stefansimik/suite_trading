### A gentle tour of the framework: feeds, strategies, and the engine

This tutorial explains how the framework works in simple, practical terms. We will
progress from the core concept (`EventFeed`) to strategies, synchronization, aggregation,
backtesting vs. live, and a few ready‑to‑copy examples.

All examples are inspired by the shipped tests and source files, so you can use them as
reliable patterns.

---

### Big picture

- You build `Strategy`(ies) that react to `Event`(s).
- You plug `EventFeed`(s) into a `Strategy`. A feed is any stream of events / data (bars, ticks,  time ticks, news, your own domain events).
- The `TradingEngine` runs all strategies. It ensures events are distributed  in chronological order
  across all feeds added to  each strategy.
- A strategy can add or remove EventFeed(s) at any time.

The one thing to really learn: `EventFeed`. This is the main and generic source of external data (bars, ticks, news, ...).
Everything else is wiring and callbacks.

---

### Why `EventFeed`(s) are powerful

The beauty of `EventFeed`(s) is their simplicity — you learn one concept that can deliver
ALL types of data into your `Strategy`:

- Historical bars from CSV files
- Live market data from brokers
- Generated demo data for testing
- Aggregated timeframes (e.g., combine 1‑minute into 5‑minute bars)
- Time notifications
- News feeds
- Really anything you can imagine

Every `EventFeed` follows the same simple protocol, no matter what kind of data it
provides.

---

### `EventFeed` in 60 seconds

File: `src/.../platform/event_feed/event_feed.py`

An `EventFeed` is a simple, non‑blocking stream of events with these methods:

- `peek() -> Optional[Event]` — Look at the next event without consuming it.
- `pop() -> Optional[Event]` — Consume and return the next event (if ready).
- `is_finished() -> bool` — True when the feed will not produce any more events.
- `close() -> None` — Free resources. Idempotent and non‑blocking.
- `remove_events_before(cutoff_time: datetime) -> None`
  - Drop events earlier than a cutoff (used when adding feeds late).
- `list_listeners() -> list[Callable[[Event], None]]`
  - Return all registered listeners for this EventFeed in registration order (read‑only view).

Implement this protocol and your data source can feed a strategy with any data (historical bars, live
ticks, time signals, news) from any data sources (like CSVs, databases, webhooks, ///)

---

### Your strategy owns its data needs

Your `Strategy` is 100% responsible for asking for the data it needs. This gives you
complete control. You can:

- Add as many `EventFeed`(s) as you want
- Add or remove feeds at any time (not just at startup)

---

### Automatic synchronization

Note on listeners and invocation order
- Implementations may still offer `add_listener`/`remove_listener` for registration convenience, but listener invocation is no longer done inside `EventFeed.pop()`.
- The `TradingEngine` is responsible for invoking EventFeed listeners. It calls `feed.list_listeners()` and invokes each listener right after the strategy callback processes the popped event.
- Ordering: listeners are invoked in the order returned by `list_listeners()` (registration order).
- Error handling: listener exceptions are caught and logged; the engine keeps running.

Here’s where the magic happens — the `TradingEngine` automatically synchronizes ALL your
added `EventFeed`(s) per `Strategy`:

1) Chronological order
   The `TradingEngine` looks across all feeds of a strategy, finds the oldest available
   event, and delivers it. You always process events in strict chronological order.

2) Independent timelines
   Each `Strategy` has its own timeline (can run at a different time). This lets you run
   historical backtests and live strategies at once, side by side.

3) Automatic cleanup and stop
   When all EventFeed(s) of a particular `Strategy` are finished (they have method `is_finished()`), they’re cleaned up automatically and
   the `Strategy` stops on its own.

---

### Ready‑made feeds you can use now

1) `BarsFromDataFrameEventFeed`
- Purpose: stream `NewBarEvent`(s) from a pandas `DataFrame` (historical bars).
- Notes:
  - Required columns: `start_dt`, `end_dt`, `open`, `high`, `low`, `close` (optional: `volume`)
  - UTC enforced; pass `source_tz` if your datetimes are naive
  - Can auto‑sort by `end_dt` (`auto_sort=True` by default)
  - Emits events with `is_historical=True`

2) `FixedSequenceEventFeed` (with create_bar_series)
- Purpose: feed synthetic demo bars by wrapping create_bar_series output into `NewBarEvent`(s).
- Uses a deque internally; `peek()` returns the next event, `pop()` consumes it.

3) `TimeBarAggregationEventFeed`
- Purpose: aggregate minute bars (e.g., 1‑min) to N‑minute bars (e.g., 5‑min).
- How it works:
  - Registers as a listener on the source feed via the implementation's `add_listener(...)` (concrete feeds may expose registration helpers even though the EventFeed Protocol only requires `list_listeners()`)
  - Accumulates OHLCV and emits on N‑minute boundaries
  - Emits `NewBarEvent` with source `dt_received` and `is_historical`
  - `emit_first_partial_bar` decides whether the very first partial bar is emitted; `emit_later_partial_bars` controls subsequent partials

4) `FixedIntervalEventFeed`
- Purpose: emit `TimeTickEvent` at a fixed interval (every second/minute, etc.).
- Great as a heartbeat/clock for scheduling logic.
- Can auto‑finish together with another feed via `finish_with_feed`.

Tip: You can set parameter `finish_with_feed` to another feed to automatically stop
generating `TimeTickEvent`(s) from this `FixedIntervalEventFeed`.

---

### Minimal example: read bars from CSV via `DataFrame`

Inspired by `tests/unit/.../load_bars_from_csv/test_bars_fom_csv.py`

```python
import logging
from pathlib import Path
import pandas as pd

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.market_data.bar.bar_event import BarEvent
from suite_trading.platform.event_feed.bars_from_dataframe_event_feed import (
    BarsFromDataFrameEventFeed,
)
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.strategy.strategy import Strategy


logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).with_name("demo_bars.csv")
INSTRUMENT = Instrument("EURUSD", "FOREX", 0.00001, 1)
BAR_TYPE = BarType(INSTRUMENT, 1, BarUnit.MINUTE, PriceType.LAST_TRADE)


class CsvStrategy(Strategy):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._count = 0

    def on_start(self):
        df = pd.read_csv(CSV_PATH, parse_dates=["start_dt", "end_dt"])
        feed = BarsFromDataFrameEventFeed(df=df, bar_type=BAR_TYPE)
        self.add_event_feed("bars_from_csv", feed)

    def on_event(self, event):
        if isinstance(event, BarEvent):
            self._count += 1
            logger.debug(f"Processed bar #{self._count}: {event.bar}")


engine = TradingEngine()
engine.add_strategy(CsvStrategy(name="csv_demo"))
engine.start()
```

Note: Strategy $name must be unique within a single TradingEngine. `TradingEngine.add_strategy`
will raise ValueError when a duplicate name is provided.

---

### Common `EventFeed` types (copy‑paste snippets in Strategy)

1) Loading historical data from CSV

```python
# Load your CSV data
df = pd.read_csv("eurusd_data.csv", parse_dates=["start_dt", "end_dt"])

# Define what kind of bars these are
instrument = Instrument("EURUSD", "FOREX", 0.00001, 1)
bar_type = BarType(instrument, 1, BarUnit.MINUTE, PriceType.LAST_TRADE)

# Create the feed
feed = BarsFromDataFrameEventFeed(df=df, bar_type=bar_type)

# Add to your strategy
self.add_event_feed("historical_data", feed)
```

2) Generating demo data

```python
from suite_trading.utils.data_generation.bar_generation import DEFAULT_FIRST_BAR, create_bar_series
from suite_trading.domain.market_data.bar.bar_event import BarEvent, wrap_bars_to_events
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed


bars = create_bar_series(first_bar=DEFAULT_FIRST_BAR, num_bars=100)
demo_feed = FixedSequenceEventFeed(wrap_bars_to_events(bars))
self.add_event_feed("demo_data", demo_feed)
```

3) Aggregating timeframes

```python
# Start with 1-minute data
minute_feed = BarsFromDataFrameEventFeed(df=minute_data, bar_type=minute_bar_type)

# Aggregate to 5-minute bars
five_minute_feed = TimeBarAggregationEventFeed(
    source_feed=minute_feed,
    unit=BarUnit.MINUTE,
    size=5,
    emit_first_partial_bar=False,  # Skip incomplete first bar
)

# Strategy receives BOTH 1-minute and 5-minute bars
self.add_event_feed("minute_data", minute_feed)
self.add_event_feed("five_minute_data", five_minute_feed)
```

4) Time notifications

```python
from datetime import datetime, timedelta, timezone

time_feed = FixedIntervalEventFeed(
    start_dt=datetime.now(timezone.utc),
    interval=timedelta(seconds=30),
)
self.add_event_feed("timer", time_feed)
```

---

### Two feeds: 1‑minute bars and aggregated 5‑minute bars

Inspired by `tests/unit/.../test_time_bar_aggregation_event_feed.py`

```python
from datetime import datetime, timezone
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.bar.bar_event import BarEvent, wrap_bars_to_events
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.platform.event_feed.time_bar_aggregation_event_feed import (
    TimeBarAggregationEventFeed,
)
from suite_trading.strategy.strategy import Strategy
from suite_trading.utils.data_generation.bar_generation import create_bar_type, create_bar, create_bar_series


class AggregationStrategy(Strategy):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.n_1m = 0
        self.n_5m = 0

    def on_start(self):
        bt_1m = create_bar_type(value=1, unit=BarUnit.MINUTE)
        first_end = datetime(2025, 1, 2, 0, 1, 0, tzinfo=timezone.utc)
        first_bar = create_bar(bar_type=bt_1m, end_dt=first_end)

        src = FixedSequenceEventFeed(wrap_bars_to_events(create_bar_series(first_bar=first_bar, num_bars=20)))
        self.add_event_feed("1m", src)

        agg = TimeBarAggregationEventFeed(
            source_feed=src,
            unit=BarUnit.MINUTE,
            size=5,
            emit_first_partial_bar=False,
        )
        self.add_event_feed("5m", agg)

    def on_event(self, event):
        if isinstance(event, BarEvent):
            unit = event.bar.bar_type.unit
            if unit == BarUnit.MINUTE:
                if int(event.bar.bar_type.value) == 1:
                    self.n_1m += 1
                if int(event.bar.bar_type.value) == 5:
                    self.n_5m += 1


engine = TradingEngine()
engine.add_strategy(AggregationStrategy(name="agg"))
engine.start()
```

What to notice:
- The aggregation feed registers as a listener on the source via the implementation's `add_listener(...)` (engine invokes listeners after strategy callback)
- The strategy receives both 1‑min and 5‑min `NewBarEvent`(s), interleaved in time order
- `emit_first_partial_bar` controls the initial partial window; `emit_later_partial_bars` controls later partials

---

### Flexible configuration (keep strategies clean)

Configure your strategy’s data sources from outside the strategy itself:

```python
class FlexibleStrategy(Strategy):
    def __init__(self, name: str, data_feeds: dict):
        super().__init__(name)
        self.data_feeds = data_feeds

    def on_start(self):
        # Add all externally configured feeds
        for name, feed in self.data_feeds.items():
            self.add_event_feed(name, feed)

# Example external wiring
feeds = {
    "minute_bars": BarsFromDataFrameEventFeed(df=df, bar_type=minute_type),
    "daily_bars": BarsFromDataFrameEventFeed(df=daily_df, bar_type=daily_type),
    "timer": FixedIntervalEventFeed(start_dt=start, interval=timedelta(minutes=1)),
}
strategy = FlexibleStrategy(data_feeds=feeds)
```

This keeps `Strategy` code reusable and it can be fed / configured for any type of input data..

---

### Adding feeds during runtime

You can add `EventFeed`(s) at any time, not just at startup. The engine maintains
chronology by calling `remove_events_before(last_event_time)` on newly added feeds so you
never receive events from “the past.”

```python
def on_event(self, event):
    if some_condition:
        new_feed = SomeOtherEventFeed(...)
        self.add_event_feed("additional_data", new_feed)

    if other_condition:
        self.remove_event_feed("old_feed")
```

---

### How strategies start and stop

You don’t need to configure any start/end dates, when Strategy should be running.
There is only one simple rule / principle:

> Each `Strategy` stops automatically when all of its `EventFeed`(s) are finished.
> `TradingEngine` stops automatically, when all added `Strategy`(s) are stopped.

Implications:
- Historical feeds finish automatically when they reach the end of data
- Time‑based feeds can finish, when they are configured (some sort of `end_dt` param)
- You can stop any EventFeed manually from Strategy by calling:
  - `feed.close()`

---

### Strategy clocks

Each strategy tracks its own timeline using the last processed event time:

- `last_event_time`: time of the last event you processed (`event.dt_event`)

You can still access the event's receive time directly from the `$event` object when needed:

```python
def on_event(self, event):
    print(f"Processing event at {self.last_event_time}")
    print(f"System received it at {event.dt_received}")
```

If you need frequent “ticks,” add `FixedIntervalEventFeed` to nudge your logic.

---

### Advanced patterns

Data aggregation chain (multiple timeframes from a single minute source):

```python
# 1-minute source data
minute_feed = BarsFromDataFrameEventFeed(df=df, bar_type=minute_type)

# Aggregate to 5-minute
five_min_feed = TimeBarAggregationEventFeed(source_feed=minute_feed, unit=BarUnit.MINUTE, size=5)

# Aggregate to 15-minute
fifteen_min_feed = TimeBarAggregationEventFeed(source_feed=minute_feed, unit=BarUnit.MINUTE, size=15)

# Strategy receives all timeframes
self.add_event_feed("1min", minute_feed)
self.add_event_feed("5min", five_min_feed)
self.add_event_feed("15min", fifteen_min_feed)
```

Aggregation rules (5‑min windows), straight from `TimeBarAggregationEventFeed`:
- Windows align to UTC days; end at minute multiples of N (e.g., 00:05, 00:10, 00:15)
- A bar ending exactly at a window boundary triggers bar emission
- First partial window emission is controlled by `emit_first_partial_bar`; later partials by `emit_later_partial_bars`


### Key benefits

1) One concept to rule them all
   Learn `EventFeed` once and handle any data source — nothing more to knoow & no special cases.

2) Perfect synchronization
   The engine guarantees chronological ordering across multiple feeds / per each Strategy.

3) Flexible timing
   - Independent timelines per `Strategy` (no global clock)
   - No start/end dates to manage — strategies stop naturally when their EventFeed(s) finish
   - Strategy can add or remove feeds anytime


---

### Choosing brokers: default, fixed, or dynamic

This way all 3 scenarios are easy to implement:

1) Default broker for Strategy
- Pass a `Broker` instance as part of your Strategy's input configuration and store it as
  your default (e.g., `$default_broker`). Use it whenever you call `submit_order`.

```python
class MyStrategy(Strategy):
    def __init__(self, name: str, default_broker: Broker) -> None:
        super().__init__(name)
        self.default_broker = default_broker  # default Broker for this Strategy

    def on_event(self, event: Event):
        if should_trade(event):
            self.submit_order(create_order(event), self.default_broker)
```

2) Fixed Broker for Strategy
- Choose a specific Broker directly inside the Strategy using `get_broker` with its concrete
  class, for example `self.get_broker(SimulatedBroker)`.

```python
# Retrieve a concrete Broker instance by its class
sim_broker = self.get_broker(SimulatedBroker)
self.submit_order(create_order(event), sim_broker)
```

3) Strategy chooses Broker dynamically
- A Strategy can implement its own logic and select from all available brokers exposed via the
  $brokers mapping.

```python
# Inspect all available brokers and choose one based on your own rules
for broker_type, broker in self.brokers.items():
    if supports_instrument(broker, event):  # example of some logic
        self.submit_order(create_order(event), broker)
        break
```

Notes:
- The $brokers property returns a mapping: dict[type[Broker], Broker].
- `get_broker(broker_type)` raises an error if the requested broker type was not added to the
  TradingEngine.
