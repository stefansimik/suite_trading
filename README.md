# SUITE Trading

**S**imple, **U**nderstandable, **I**ntuitive **T**rading **E**ngine

> ⚠️ **Work in Progress** (as of 2025-10-31): This project is in active development (~75-80%
> complete). Core event-driven architecture, strategy framework, and broker integration with
> simulated execution are implemented.

## Overview

SUITE Trading is a modern algorithmic trading framework built on **event-driven architecture** with **independent strategy timelines**. Designed with simplicity, understandability, and intuitive use in mind, it provides a unified interface for both backtesting strategies with historical data and running live trading operations.

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
            interval=timedelta(seconds=10),  # Le'ts have time notifications each 10 seconds
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

## Key Features

- **Unified trading scenarios**: Single strategy design supports all trading modes:
  - **Backtesting**: Historical data + simulated broker execution
  - **Paper trading**: Live data + simulated broker execution
  - **Live trading**: Live data + live broker execution
- **Flexible architecture**: Each strategy can connect to:
  - **Multiple market data sources**: Receive data from one or more data providers simultaneously
  - **Multiple brokers**: Submit orders to one or more connected brokers
- **Event-driven architecture**: Chronological event processing with automatic ordering and syncing after adding new data sources during runtime
- **Independent strategy timelines**: Each strategy maintains its own timeline and processes events independently, allowing simultaneous backtests and live strategies
- **Comprehensive and intuitive domain models**: Complete Event, Order, Instrument, and Market Data hierarchies
- **Strategy framework**: Lifecycle management with `on_start()`, `on_stop()`, `on_error()`, and universal `on_event()` methods
- **Broker agnostic**: Framework designed to work with multiple brokers
- **Python native**: Built specifically for Python with type hints throughout

## Architecture

Additional docs:
- FAQ: docs/FAQ.md
- Bar interval convention: docs/bar-time-intervals.md

SUITE Trading uses an **event-driven architecture**.

- All market data flows through timestamped `Event` objects into `Strategy` callbacks (default `on_event()` method).
- Each `Strategy` runs in isolation from other strategies
- Each `Strategy` processes own events in chronological order (sorted by `Event.dt_event`) and maintains its own timeline
- Source of events for each strategy is an `EventFeed`. One strategy can have multiple `EventFeed`s.

### Core Philosophy

- **Event-driven architecture**: All market data flows through timestamped events
- **Independent strategy timelines**: Each strategy operates with its own chronological timeline
- **Domain-driven design**: Clear separation between business logic and technical infrastructure
- **User-centric API**: Designed for developer convenience

### Core Components

- `TradingEngine`: Central coordinator that manages Strategy(ies), EventFeed(s), and broker(s).
- `Strategy`: Base class with an independent timeline and a universal `on_event()` method.
- `EventFeed`: Strategy-attached data source that delivers chronologically ordered events to a
  Strategy, optionally applying timeline filters. It can consume one or more EventFeedProvider(s).
- `EventFeedProvider`: Producer of chronologically ordered event streams (historical or live).
- `Event`: Base class for all market data (Bar, TradeTick, QuoteTick) with chronological sorting.
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

**2. Broker integration** — Order execution
```
Strategy → generates Orders → Broker (Live / Simulated) → publish ExecutionEvent
```
- Real-time order placement and execution with multiple brokers
- Order state management and fill event processing
- Position and portfolio tracking

**3. MessageBus** — Publish/subscribe event delivery
```
Publishers → MessageBus Topics → Subscribers → Event Handlers
```
- Topic-based routing with wildcard patterns (`bar::EURUSD@FOREX::5-MINUTE::LAST`)
- Especially suitable for live events and live trading coordination
- Decoupled communication between system components

### Timeline independence

Each strategy maintains its own independent timeline, which allows running simultaneously without interference:

- Multiple backtests (with historical data in different periods)
- Live strategies
- Mixed backtesting and live trading

Events are processed sequentially within each strategy's timeline:
- **Events**: All market data inherits from `Event` with `dt_event` and `dt_received` timestamps
- **Strategies**: Independent entities with their own timeline processing events sequentially
- **EventFeeds**: Data sources that provide chronologically ordered events to strategies
- **Timeline isolation**: Each strategy processes its own timeline independently from others

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

This project is in **active development** with approximately **75-80% of core functionality** implemented.

### Development status & roadmap

Current status (as of 2025-10-31):
- Ready to try: TradingEngine, Strategy lifecycle, Event model (Bar/TradeTick/QuoteTick),
  EventFeed(s), MessageBus, demo data utilities (create_bar_series + FixedSequenceEventFeed),
  SimBroker with MARKET order execution, position tracking, and per-strategy execution history.
- Not yet available: EventFeedProvider(s) for live/historical integrations, live brokers,
  advanced order execution (LIMIT/STOP orders in SimBroker), indicators, performance analytics.

**Completed:**
- ✅ Complete event-driven architecture with chronological processing
- ✅ Comprehensive domain models (Event, Bar, Order hierarchy, Instrument, Monetary)
- ✅ TradingEngine with multi-strategy management and independent timelines
- ✅ Strategy framework with lifecycle management (`on_start`, `on_stop`, `on_error`)
- ✅ Message Bus with topic-based routing and wildcard patterns
- ✅ EventFeed system with timeline filtering and management
- ✅ State machines for engine and strategy lifecycle control
- ✅ Market data events (Bar, TradeTick, QuoteTick) with proper event wrappers
- ✅ Broker protocol with unified interface for all broker implementations
- ✅ SimBroker for backtesting/paper trading with MARKET order execution
- ✅ Order state machine and execution tracking
- ✅ Position tracking and management per instrument
- ✅ Per-strategy execution history in TradingEngine
- ✅ Market depth model for simulated order matching (ZeroSpreadMarketDepthModel)

**Next Priority (Roadmap):**
1. **EventFeedProvider(s)** ❌ — Real-time market data integration
2. **Broker execution enhancements** 🔄 — Complete SimBroker (LIMIT/STOP order matching,
   cancel/modify operations) + live broker implementations
3. **Advanced order types** 🔄 — Order types are defined; need full SimBroker matching support for
   LIMIT, STOP, STOP_LIMIT orders
4. **Indicators library** ❌ — Built-in technical indicators (SMA, EMA, RSI, MACD); composable API
5. **Performance analytics** ❌ — Strategy performance metrics and reporting

## License

See [LICENSE](LICENSE) file for details.

## Disclaimer

This software is for educational and research purposes. Use at your own risk in any live trading environments.
