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

## Core Development Principles

### KISS, YAGNI, DRY
- **KISS**: Always prefer the simplest working solution
- **YAGNI**: Only implement when actually needed
- **DRY**: Single representation for each piece of knowledge
- **Composition Over Inheritance**: Prefer composition over inheritance hierarchies
- **Fail Fast**: Detect and report errors immediately
- **Intuitive Domain Model**: Create simple, understandable domain models
- **Broker Agnostic**: Framework should be broker agnostic where possible
- **Single Responsibility**: Each class has one reason to change
- **Separation of Concerns**: Clear responsibility boundaries between classes

### User-Centric Design Principle
**APIs should be designed for the user, not for internal implementation convenience.**

When there's tension between internal simplicity and external usability, favor the user-centric approach if cost is low and user benefit is clear.

## Coding Standards

### Standard Classes Only
**Rule: Use standard classes exclusively. No dataclasses allowed.**

This ensures complete consistency and aligns with core principles of explicit code and predictable behavior.

### Documentation Style
- Use Google documentation style for all docstrings
- Format docstrings with content on separate lines
- Write in natural language that's easy to understand
- Use simple words and explain concepts clearly
- Make benefits concrete and specific

### String Representation Methods
Use `self.__class__.__name__` instead of hardcoded class names in `__str__` and `__repr__` methods for better maintainability.

### Exception Message Formatting
All error messages must follow this format:
1. **Function Context**: Use backticks around function names: `` `function_name` ``
2. **Variable Identification**: Prefix variables with `$`: `$market_data_provider`
3. **Variable Values**: Include actual values: `f"$bar_type ({bar_type})"`
4. **Root Cause**: State what's None or what condition failed
5. **Solution Guidance**: Provide actionable advice

Example: `f"Cannot call \`subscribe_to_bars\` for $bar_type ({bar_type}) because $market_data_provider is None. Set a market data provider when creating TradingEngine."`

### Import and Package Structure
- **No Re-exports**: Import classes directly from their source modules
- **Namespace Packages**: Only create `__init__.py` files with executable code
- Each import should clearly show where classes come from

### Comment and Parameter Formatting
- Use exactly 2 spaces before `#` for inline comments
- Put each parameter on separate line for functions with many parameters
- Use sentence case for section comments

### Testing Guidelines
- Use `pytest` library (not `unittest`)
- Test function names start with "test_" and describe what they're testing
- Organize in `tests/unit/` and `tests/integration/`
- Mirror the package structure being tested

### Git Commit Guidelines
- Write in imperative mood (like giving a command)
- Keep subject line concise (50 chars or less)
- Start with capital letter, no period at end
- Use present tense verbs: Add, Fix, Remove, Update

## Development Status
This is an early-stage project, where core architecture and main components are being designed and implemented.
