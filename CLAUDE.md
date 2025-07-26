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
- **DRY**: Eliminate duplication of information, logic or business rules across the codebase
- **Composition Over Inheritance**: Prefer composition over inheritance hierarchies
- **Fail Fast**: Detect and report errors immediately
- **Intuitive Domain Model**: Create simple, understandable domain models
- **Broker Agnostic**: Framework should be broker agnostic where possible
- **Single Responsibility**: Each class has one reason to change
- **Separation of Concerns**: Clear responsibility boundaries between classes
- **Principle of Least Surprise**: Code should behave in ways that users naturally expect

### User-Centric Design Principle
**APIs should be designed for the user, not for internal implementation convenience.**

Guides decisions when there's tension between internal simplicity and external usability.
Example: `execution.side` feels natural vs. `execution.order.side` feels awkward.

#### Decision Framework
1. **Identify user mental model** - How do users think about this?
2. **Assess implementation cost** - Is the user-friendly approach expensive?
3. **Consider consistency** - Does this fit existing APIs?
4. **Evaluate maintenance** - Will this create ongoing complexity?
5. **Balance principles** - How does this interact with KISS/YAGNI/DRY?

**Rule:** If cost is low and user benefit is clear, favor the user-centric approach.

## Coding Standards

### Naming Conventions
**Rule: All names (functions, variables, classes) should be as simple as possible, predictable, and self-documenting.**

The purpose of any name should be immediately clear and indicate what it does or contains.

#### Guidelines
- **Use clear, descriptive names**: Choose names that explain the purpose without needing comments
- **Avoid abbreviations**: Write `user_count` instead of `usr_cnt` or `uc`
- **Use verbs for functions**: Functions should describe what they do (`calculate_total`, `send_message`)
- **Use nouns for variables**: Variables should describe what they contain (`total_amount`, `user_list`)
- **Be specific**: Use `trading_engine` instead of `engine`, `bar_data` instead of `data`
- **Follow conventions**: Use standard Python naming patterns (snake_case for functions/variables)

#### Examples
```python
# ✅ Good - clear and self-documenting
def calculate_portfolio_value(positions: list) -> Decimal:
    total_value = Decimal('0')
    for position in positions:
        market_price = get_current_price(position.instrument)
        position_value = position.quantity * market_price
        total_value += position_value
    return total_value

# ❌ Bad - unclear and abbreviated
def calc_pv(pos: list) -> Decimal:
    tv = Decimal('0')
    for p in pos:
        mp = get_price(p.inst)
        pv = p.qty * mp
        tv += pv
    return tv
```

### Standard Classes Only
**Rule: Use standard classes exclusively. No dataclasses allowed.**

This ensures complete consistency and aligns with core principles of explicit code and predictable behavior.

### Documentation Style
- Use Google documentation style for all docstrings
- Format docstrings with content on separate lines
- Include purpose, parameters, return values, and exceptions in function docstrings
- Include type information for all parameters, return values, and attributes in docstrings

#### Docstring Writing Style
Write docstrings that are easy to understand for everyone:
- **Use natural language**: Write like you're explaining to a colleague, not like a technical manual
- **Use simple words**: Replace complex terms with everyday words that anyone can understand
- **Write for beginners**: Assume the reader is learning - explain concepts clearly and simply
- **Make benefits concrete**: Explain what something does and why it matters in clear, specific terms

**Examples:**
- ✅ "Engine makes sure the provider is available" instead of "Engine validates provider availability"
- ✅ "Simple way to get events from different sources" instead of "Unified interface for event retrieval with permanent closure detection"

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

#### No Re-exports Rule
- **Never use re-exports in `__init__.py` files**
- Each class/function should be imported directly from its source module
- This eliminates import ambiguity and ensures consistent import patterns across the codebase

**Benefits:**
- **Zero Ambiguity**: Exactly one way to import each class
- **Clear Dependencies**: Import statements clearly show where each class comes from
- **Zero Maintenance**: No need to maintain `__all__` lists or coordinate exports
- **IDE Friendly**: Auto-completion and "Go to Definition" work perfectly

**Examples:**
```python
# ✅ Good - direct imports from source modules
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.order.order_enums import OrderSide

# ❌ Bad - re-exports (not allowed)
from suite_trading import TradingEngine  # Would require re-export
from suite_trading.domain import Bar     # Would require re-export
```

#### Package Structure and `__init__.py` Files
**Rule: Only create `__init__.py` files when they contain executable code.**

Create `__init__.py` files **only** for:
- **Executable code** (imports, variable assignments, function calls)
- **Version information** (root package only: `__version__ = "1.0.0"`)
- **Package initialization logic**

**Don't create** `__init__.py` files that contain only docstrings, comments, or are empty.

Use **namespace packages** (PEP 420) for directory organization - no `__init__.py` needed.

**Examples:**
```python
# ✅ Good - executable code
# src/suite_trading/__init__.py
__version__ = "0.0.1"

# ✅ Good - namespace packages (no __init__.py)
# src/suite_trading/domain/
# src/suite_trading/platform/

# ❌ Bad - only docstring
# src/suite_trading/domain/__init__.py
"""Domain objects."""  # Delete this file
```

### Comment and Parameter Formatting
- Use consistent indentation for inline comments
- Always use exactly 2 spaces before the `#` symbol for inline comments
- Align all inline comments in the same code block consistently
- Use sentence case for section comments (not title case)

#### Example
```python
# Order identification  # ← sentence case for sections
order_id: str  # Unique identifier for the order
side: OrderDirection  # Whether this is a BUY or SELL order
```

### Parameter Formatting
- When functions have many parameters, put each parameter on a separate line for better readability
- This applies to function definitions, method definitions, and class constructors
- Maintain consistent indentation for all parameters
- Add a trailing comma after the last parameter in multi-line parameter lists
- For long function names, use proper spacing and alignment

#### Examples
```python
# ❌ Wrong - multiple parameters on same line
def __init__(self, instrument: Instrument, side: OrderDirection, quantity: Decimal,
             order_id: int = None) -> None:

# ✅ Good - each parameter on separate line with trailing comma
def __init__(
    self,
    instrument: Instrument,
    side: OrderDirection,
    quantity: Decimal,
    order_id: int = None
) -> None:

# ✅ Good - long function names with proper formatting
def get_historical_bars_series(
    self,
    instrument: Instrument,
    from_dt: datetime,
    until_dt: datetime,
) -> Sequence[Bar]:
    ...
```

### Markdown Formatting
**Rule: All generated Markdown content must have a maximum line length of 100 characters.**

**Why:** Consistent line length improves readability and ensures proper formatting across different editors and viewing environments.

#### Requirements
- **Line Length Limit**: No line should exceed 100 characters
- **Automatic Line Breaks**: Add newlines after reaching 100 characters
- **Preserve Readability**: Break lines at natural points (spaces, punctuation) when possible
- **Code Blocks**: Code examples within Markdown should also follow this rule
- **Lists and Headers**: Apply the same 100-character limit to all content types

### Testing Guidelines
- Don't generate tests unless explicitly asked
- Use `pytest` library (not `unittest`)
- Test function names start with "test_" and describe what they're testing
- Organize in `tests/unit/` and `tests/integration/`
- Mirror the package structure being tested
- Keep only the root `tests/__init__.py` file

### Git Commit Guidelines
- Write commits in **imperative mood** (like giving a command)
  - **✅ Good:** "Add user authentication"
  - **❌ Avoid:** "Added user authentication"
- Keep subject line concise (50 chars or less)
- Start with capital letter, no period at end
- Use present tense imperative verbs: Add, Fix, Remove, Update
- Be descriptive about what and why
- For longer commits, add body separated by blank line

## Development Status
This is an early-stage project, where core architecture and main components are being designed and implemented.
