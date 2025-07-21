# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Package Management
- Install dependencies: `uv sync`
- Run Python scripts: `uv run <script>`
- Add dependencies: `uv add <package>`

### Testing
- Run all tests: `uv run pytest`
- Run specific test: `uv run pytest tests/path/to/test_file.py`
- Run tests with specific pattern: `uv run pytest -k "test_pattern"`

### Code Quality
- Linting and formatting are handled by Ruff (configured in pyproject.toml)
- Line length limit: 150 characters
- Python path includes `src/` for imports

### Project Building
- Build package: `uv build`
- Python version requirement: 3.13.x (exact version match required)

## Architecture Overview

### Core Design Philosophy
SUITE Trading follows a clean, event-driven architecture with these key principles:
- **Event-driven**: All market data flows through events with timestamps (`dt_received`, `dt_event`)
- **Publisher-subscriber**: MessageBus handles event distribution with topic-based routing
- **Demand-based subscriptions**: Data publishing only occurs when strategies subscribe
- **Domain-driven design**: Clear separation between domain objects and platform services

### Key Components

#### Domain Layer (`src/suite_trading/domain/`)
- **Events**: All objects inherit from `Event` base class with `dt_received` and `dt_event` timestamps
- **Market Data**: Bars, trade ticks, quote ticks with corresponding event wrappers
- **Instruments**: Financial instrument definitions
- **Orders**: Order management and execution tracking (planned)
- **Monetary**: Currency and money handling with registry pattern

#### Platform Layer (`src/suite_trading/platform/`)
- **TradingEngine**: Central coordinator managing strategies and subscriptions
- **MessageBus**: Topic-based event routing with wildcard support and priority ordering
- **Event Feed**: Market data streaming interface (planned)

#### Strategy Framework (`src/suite_trading/strategy/`)
- **Base Strategy**: Abstract base with subscription management and event routing
- Strategies subscribe to data via `subscribe_bars()`, `subscribe_trade_ticks()`, etc.
- Event callbacks: `on_bar()`, `on_trade_tick()`, `on_quote_tick()`, `on_event()`

### Data Flow Architecture

1. **Market Data** → **Event Wrappers** → **MessageBus Topics** → **Strategy Callbacks**
2. **Subscription Management**: TradingEngine tracks which strategies need which data
3. **Event Routing**: MessageBus uses topic patterns like `bar::EURUSD@FOREX::5-MINUTE::LAST`
4. **Automatic Cleanup**: Strategies automatically unsubscribe on stop

### Topic Naming Convention
Topics use `::` separator with pattern: `{type}::{instrument}::{timeframe}::{price_type}`
- Example: `bar::EURUSD@FOREX::5-MINUTE::LAST`
- Supports wildcards: `bar::*::5-MINUTE::*`

### Event Processing Order
Events are sorted chronologically by:
1. Primary: `dt_event` (official event time)
2. Secondary: `dt_received` (system arrival time)

## Key Patterns

### String Representations
All domain objects implement consistent `__str__()` methods:
- BarType: `"EURUSD@FOREX::5-MINUTE::LAST"`
- Instrument: `"SYMBOL@MARKET"`

### Subscription Pattern
Strategies use a two-phase subscription system:
1. Subscribe via TradingEngine (handles MessageBus and tracking)
2. Local tracking for automatic cleanup on strategy stop

### Event Wrapper Pattern
Raw market data (Bar, TradeTick) is wrapped in event objects (NewBarEvent, NewTradeTickEvent) that include timing metadata and are routed through the MessageBus.

## Development Status
This is an early-stage project (~5% complete). Core architecture is established but major components like market data providers, execution engine, and clock system are not yet implemented.
