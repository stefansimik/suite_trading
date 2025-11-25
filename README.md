# SUITE Trading

**S**imple, **U**nderstandable, **I**ntuitive **T**rading **E**ngine

> ⚠️ **Work in Progress** (as of 2025-11-26): This project is in active development (~80–85% complete).

## Overview

SUITE Trading is a modern algorithmic trading framework built on **event-driven architecture** with a **single shared engine timeline**. Designed with simplicity, understandability, and intuitive use in mind, it provides a unified interface for both backtesting strategies with historical data and running live trading operations.

## Getting Started

### Requirements

- Python 3.13.x (exact)
- Dependencies managed via `uv` (see `pyproject.toml`)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd suite_trading

# Install dependencies
uv sync

# Verify installation by running tests
uv run pytest
```

### Basic Usage

```python
import logging
from datetime import timedelta

from suite_trading.domain.market_data.bar.bar_event import BarEvent, wrap_bars_to_events
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.utils.data_generation.bar_generation import create_bar_series
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.platform.event_feed.periodic_time_event_feed import FixedIntervalEventFeed
from suite_trading.strategy.strategy import Strategy


logger = logging.getLogger(__name__)


class DemoStrategy(Strategy):

    # Standard callback, when strategy starts.
    def on_start(self):
        logger.debug("Strategy starting...")

        # Add data to strategy: 1-minute bars (demo data)
        bars_feed: EventFeed = FixedSequenceEventFeed(wrap_bars_to_events(create_bar_series(num_bars=20)))
        self.add_event_feed("bars_feed", bars_feed)

        # Add data to strategy: Time notifications each 10 seconds
        time_feed: EventFeed = FixedIntervalEventFeed(
            start_dt=bars_feed.peek().bar.end_dt,  # Align first time notification with first bar
            interval=timedelta(seconds=10),  # Let's have time notifications every 10 seconds
            finish_with_feed=bars_feed,  # Stop time notifications, when $bars_feed is finished
        )
        self.add_event_feed("time_feed", time_feed)

    # Standard callback for all events
    def on_event(self, event):
        if isinstance(event, BarEvent):
            self.on_bar(event.bar)  # Dispatch to custom callback
        else:
            # Handle all other events here
            logger.debug(f"Received (unhandled) event: {event}")

    # Custom handler for bars
    def on_bar(self, bar):
        logger.debug(f"Received bar: {bar}")

    # Standard callback, when strategy stops
    def on_stop(self):
        logger.debug("Strategy stopping...")


# Create and run the trading engine
engine: TradingEngine = TradingEngine()
engine.add_strategy(DemoStrategy(name="demo_strategy"))
engine.start()
```

Note: Strategy $name must be unique within a single TradingEngine. The engine enforces
this and raises ValueError on duplicates when you call `add_strategy`.

### Trading with SimBroker (quick demo)

The framework ships with a feature-complete SimBroker. It supports MARKET, LIMIT, STOP, and
STOP_LIMIT orders, plus cancel/modify operations, margin, and fees. The engine automatically
converts incoming market-data events to OrderBook snapshot(s) for order-price matching when a
broker implements `OrderBookDrivenBroker`.

```python
import logging
from datetime import timedelta
from decimal import Decimal

from suite_trading.domain.market_data.bar.bar_event import BarEvent, wrap_bars_to_events
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.domain.order.orders import MarketOrder, LimitOrder
from suite_trading.platform.broker.sim.sim_broker import SimBroker
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.platform.event_feed.periodic_time_event_feed import FixedIntervalEventFeed
from suite_trading.utils.data_generation.bar_generation import create_bar_series
from suite_trading.strategy.strategy import Strategy


logger = logging.getLogger(__name__)


class TradingDemo(Strategy):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._submitted = False

    def on_start(self):
        bars = FixedSequenceEventFeed(wrap_bars_to_events(create_bar_series(num_bars=10)))
        self.add_event_feed("bars", bars)
        self.add_event_feed("timer", FixedIntervalEventFeed(start_dt=bars.peek().bar.end_dt, interval=timedelta(seconds=5), finish_with_feed=bars))

    def on_event(self, event):
        if isinstance(event, BarEvent) and not self._submitted:
            # Place a MARKET buy for 1 unit on the first bar
            order = MarketOrder(event.bar.instrument, OrderSide.BUY, Decimal("1"))
            self.submit_order(order, self.get_broker("sim"))
            # Also place a LIMIT sell slightly above close as an example
            limit_px = event.bar.close * Decimal("1.001")
            limit = LimitOrder(event.bar.instrument, OrderSide.SELL, Decimal("1"), limit_px)
            self.submit_order(limit, self.get_broker("sim"))
            self._submitted = True


engine = TradingEngine()
engine.add_broker("sim", SimBroker())  # One simulated account
engine.add_strategy(TradingDemo(name="sim_demo"))
engine.start()
```

## Key Features

- Unified trading scenarios with one Strategy API:
  - Backtesting: historical data + SimBroker
  - Paper trading: live data + SimBroker
  - Live trading: live data + live broker(s)
- Flexible connectivity per strategy:
  - Multiple EventFeed(s) from different providers at once
  - Multiple broker(s) per engine; strategies can choose brokers dynamically
- Event-driven architecture: strict chronological processing across all strategies and feeds in one engine
- Concurrent strategies on one shared timeline: run multiple backtests and live strategies side by side
- Event→OrderBook conversion in engine for brokers that do order-book-driven matching
- SimBroker with MARKET, LIMIT, STOP, STOP_LIMIT, cancel/modify, margin, and fees
- Comprehensive domain models: Event hierarchy, Orders, Instruments, Money/Account/Position
- Strategy framework: `on_start()`, `on_stop()`, `on_error()`, and universal `on_event()`
- MessageBus with topic factory and wildcard routing for decoupled pub/sub
- Python-native design with modern type hints throughout

## Architecture

Additional docs:
- FAQ: docs/FAQ.md
- Bar interval convention: docs/bar-time-intervals.md

SUITE Trading uses an **event-driven architecture**.

- All market data flows through timestamped `Event` objects into `Strategy` callbacks (default `on_event()` method).
- Strategies are isolated in code and state but share one engine timeline
- The `TradingEngine` advances one global "now" using `Event.dt_event` (ties by `dt_received`); strategies do not manage time
- Source of events for each strategy is an `EventFeed`. One strategy can have multiple `EventFeed`s.

### Core Philosophy

- **Event-driven architecture**: All market data flows through timestamped events
- **Single shared timeline**: Engine schedules events globally; strategies react
- **Domain-driven design**: Clear separation between business logic and technical infrastructure
- **User-centric API**: Designed for developer convenience

### Core Components

- `TradingEngine`: Central coordinator that manages Strategy(ies), EventFeed(s), and broker(s).
- `Strategy`: Base class without its own clock and a universal `on_event()` method.
- `EventFeed`: Strategy-attached data source that delivers chronologically ordered events to a
  Strategy, optionally applying timeline filters. It can consume one or more EventFeedProvider(s).
- `EventFeedProvider`: Producer of chronologically ordered event streams (historical or live).
- `Event`: Base class for all market data (Bar, TradeTick, QuoteTick) with chronological sorting.
- `Event→OrderBook converter`: Converts Bar/TradeTick/QuoteTick events to OrderBook snapshot(s)
- `MessageBus`: Topic-based routing system with wildcard patterns
  (`bar::EURUSD@FOREX::5-MINUTE::LAST`).
- `Domain models`: Financial object hierarchy (Instruments, Orders, Money, etc.).

### Data Flow

SUITE Trading provides **three main data flow paths** for different use cases:

1. EventFeed
2. Broker integration
3. MessageBus

**1. EventFeed** — Strategy-attached event source
```
EventFeed produces Events → which are delivered to Strategy.on_event()
```

Listener delivery note: The TradingEngine invokes EventFeed listeners right after it delivers the event to the owning Strategy callback; EventFeed implementations must not self-notify.

**2. Broker integration** — Order execution
```
Strategy → generates Orders → Broker (Live / Simulated) → publish ExecutionEvent
```
- Real-time order placement and execution with multiple brokers
- Order state management and fill event processing (including cancel/modify)
- Position and portfolio tracking

Note: When a broker implements `OrderBookDrivenBroker`, the engine uses its Event→OrderBook
converter to transform incoming market-data events into OrderBook snapshot(s). Brokers then
perform price matching using best bid/ask (or mid price for triggers) according to order type.

**3. MessageBus** — Publish/subscribe event delivery
```
Publishers → MessageBus Topics → Subscribers → Event Handlers
```
- Topic-based routing with wildcard patterns (`bar::EURUSD@FOREX::5-MINUTE::LAST`)
- Especially suitable for live events and live trading coordination
- Decoupled communication between system components

### Single shared timeline

All strategies attached to one `TradingEngine` advance on a single shared simulated timeline:

- Multiple backtests and live strategies can run together; their events interleave on the shared engine timeline
- Mixed backtesting and live trading are supported in one engine run

Event processing on the shared timeline:
- **Events**: All market data inherits from `Event` with `dt_event` and `dt_received` timestamps
- **Engine**: Picks the earliest available event across all active feeds and strategies (order by `dt_event`, then `dt_received`) and updates the global time
- **Strategies**: Do not advance time; they simply react to events delivered by the engine
- **EventFeeds**: Provide chronologically ordered events; when a feed is added mid‑run, the engine calls `remove_events_before(last_event_time)` so no past events are emitted

## Development & Testing

### Running tests

The project includes comprehensive test configuration with built-in logging support. Test logging is configured in `[tool.pytest.ini_options]` section of `pyproject.toml`.

| Scenario                                 | Command                                                                             |
|:-----------------------------------------|:------------------------------------------------------------------------------------|
| Run all tests (default INFO logging)     | `uv run pytest`                                                                     |
| Run a specific test file                 | `uv run pytest tests/test_basic_flow.py`                                            |
| Run a specific test function from a file | `uv run pytest tests/test_basic_flow.py::test_basic_flow` |

Note: You can append `--log-cli-level=DEBUG` to any command above to override the logging level.

Tip: See an end-to-end runnable example under tests:
- `tests/integration/suite_trading/test_playground.py`

**Available log levels:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Project Status

This project is in **active development** with approximately **80–85% of core functionality** implemented.

### Development status & roadmap

Current status (as of 2025-11-26):
- Ready to try: TradingEngine, Strategy lifecycle, Event model (Bar/TradeTick/QuoteTick),
  EventFeed(s), MessageBus, demo data utilities (`create_bar_series` + `FixedSequenceEventFeed`),
  Event→OrderBook conversion in engine, SimBroker with MARKET/LIMIT/STOP/STOP_LIMIT matching,
  cancel/modify operations, per-instrument Positions, Account with margin/fees, and per-strategy
  execution history in the engine.
- Not yet available: Concrete EventFeedProvider implementations for live/historical integrations,
  live broker integrations, indicators, performance analytics.

**Completed:**
- ✅ Event-driven architecture with chronological processing on one shared engine timeline
- ✅ Domain models (Event hierarchy, Bar, Orders, Instrument, Money/Account/Position)
- ✅ TradingEngine with multi-strategy management and routing of executions/order updates
- ✅ Strategy framework (`on_start`, `on_stop`, `on_error`, `on_event`)
- ✅ MessageBus with topic-based routing and wildcard patterns
- ✅ EventFeed system with timeline filtering and management
- ✅ Lifecycle state machines for engine and strategies
- ✅ Market data events (Bar, TradeTick, QuoteTick) with wrappers
- ✅ Broker protocol with unified interface; OrderBook-driven matching support
- ✅ SimBroker with MARKET/LIMIT/STOP/STOP_LIMIT + cancel/modify + margin/fees
- ✅ Per-instrument position tracking and per-strategy execution history
- ✅ MarketDepthModel (PassThrough) and default Margin/Fee models

**Next Priority (Roadmap):**
1. **EventFeedProvider(s)** ❌ — Implement live/historical market data integrations
2. **Live brokers** ❌ — Real broker implementations against popular venues/APIs
3. **Indicators library** ❌ — Built-in technical indicators (SMA, EMA, RSI, MACD)
4. **Performance analytics** ❌ — Strategy/backtest performance metrics and reporting

## License

See [LICENSE](LICENSE) file for details.

## Disclaimer

This software is for educational and research purposes. Use at your own risk in any live trading environments.
