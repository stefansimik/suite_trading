# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Package Management
- Install dependencies: `uv sync`
- Run Python scripts: `uv run <script>`
- Add dependencies: `uv add <package>`
- Build package: `uv build`

### Testing
- Run all tests: `uv run pytest`
- Run specific test: `uv run pytest tests/path/to/test_file.py`
- Run tests with pattern: `uv run pytest -k "test_pattern"`

### Code Quality
- Linting and formatting: Ruff (configured in pyproject.toml)
- Line length limit: 150 characters
- Python path includes `src/` for imports

### Project Requirements
- Python version: 3.13.x (exact version match required)
- Dependency manager: uv
- Test framework: pytest

## Project Overview

SUITE Trading is a **S**imple, **U**nderstandable, **I**ntuitive **T**rading **E**ngine - a modern
algorithmic trading framework built in Python for backtesting and live trading.

### Core Philosophy
- **Event-driven architecture**: All market data flows through timestamped events
- **Independent strategy timelines**: Each strategy operates with its own chronological timeline
- **Domain-driven design**: Clear separation between business logic and technical infrastructure
- **User-centric API**: Designed for developer convenience, not internal implementation ease

## Architecture Overview

### Key Components

#### Domain Layer (`src/suite_trading/domain/`)
- **Events**: Base `Event` class with `dt_received` and `dt_event` timestamps
- **Market Data**: `Bar`, `TradeTick`, `QuoteTick` with event wrappers
- **Instruments**: Financial instrument definitions with trading specifications
- **Orders**: Comprehensive order hierarchy with state machine management
- **Monetary**: Currency handling with `Money` and `CurrencyRegistry`

#### Platform Layer (`src/suite_trading/platform/`)
- **TradingEngine**: Central coordinator managing strategies and event processing
- **MessageBus**: Topic-based event routing with wildcard pattern support
- **EventFeed**: Market data streaming interface with timeline management

#### Strategy Framework (`src/suite_trading/strategy/`)
- **Strategy**: Base class with independent timeline and lifecycle management
- **Event handling**: Universal `on_event()` method with automatic routing
- **Lifecycle hooks**: `on_start()`, `on_stop()`, `on_error()` methods

### Data Flow

1. **Market Data** → **Event Wrappers** → **MessageBus Topics** → **Strategy Callbacks**
2. **Timeline Management**: Each strategy maintains independent event chronology
3. **Topic Routing**: Pattern-based routing (`bar::EURUSD@FOREX::5-MINUTE::LAST`)
4. **State Management**: Robust lifecycle control for all components

### Event Processing
- **Chronological ordering**: Events sorted by `dt_event` then `dt_received`
- **Independent timelines**: Strategies can operate at different time points
- **Automatic cleanup**: Resources released when strategies stop

## Development Principles

### Golden Rules
- **KISS**: Prefer the simplest working solution
- **YAGNI**: Implement only when actually needed
- **DRY**: Eliminate duplication of information, logic, and business rules
- **Fail fast**: Detect and report errors immediately
- **Single responsibility**: Each class has one reason to change
- **User-centric design**: APIs designed for users, not internal convenience

### Breaking Changes Allowed
During initial development, backward compatibility is out of scope. Remove or redesign
anything to get the design right.

## Coding Standards

### Naming Conventions
**Rule: Names must be simple, predictable, and self-documenting.**

- Use clear, descriptive names that explain purpose without comments
- Avoid abbreviations: `user_count` not `usr_cnt`
- Verbs for functions: `calculate_portfolio_value()`
- Nouns for variables: `total_amount`, `instrument_list`
- Be specific: `trading_engine` not just `engine`
- Follow Python conventions: snake_case for functions/variables

Example:
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

### Classes, Dataclasses, and Named Tuples
**Rule: Use standard classes for fundamental domain models. Dataclasses and named tuples are
allowed for simple config or helper/value objects.**

Why:
- Core domain needs explicit initialization and validation.
- Dataclasses/named tuples can reduce boilerplate for auxiliary data without hiding intent.

### String Interpolation
**Rule: Always use f-strings. Never use old-style interpolation.**

Applies everywhere: logs, exceptions, messages, general strings.

```python
# ✅ Good
logger.info(f"Started strategy '{strategy_name}'")

# ❌ Bad
logger.info("Started strategy '%s'", strategy_name)
logger.info("Started strategy '{}'".format(strategy_name))
```

#### Log call formatting
If the logged message has only 1 line, keep the full logger call on a single line.

Wrong:
```python
logger.debug(
    f"Event feed '{feed_name}' for strategy {strategy.__class__.__name__} was already finished or removed - no action needed",
)
```

Correct:
```python
logger.debug(f"Event feed '{feed_name}' for strategy {strategy.__class__.__name__} was already finished or removed - no action needed")
```

Note (exception): This rule does not apply when using implicit string concatenation across
adjacent string literals inside parentheses to keep long messages readable.

Allowed (implicit concatenation):
```python
logger.info(
    f"TradingEngine STOPPED; strategies stopped={stopped}, "
    f"brokers disconnected={disconnected_brokers}, "
    f"event-feed-providers disconnected={disconnected_providers}",
)
```

### Parameter Formatting
For functions with multiple parameters, use one parameter per line with trailing comma:

```python
def __init__(
    self,
    instrument: Instrument,
    side: OrderDirection,
    quantity: Decimal,
    order_id: int | None = None,
) -> None:
    ...
```

### String Representation Methods
Use `self.__class__.__name__` for maintainability:

```python
def __str__(self) -> str:
    return f"{self.__class__.__name__}(bar={self.bar}, dt_received={self.dt_received})"
```

### Docstrings (API Documentation)
**Rule: Docstrings document public APIs for external developers using your code.**

Key principles:
- Use Google-style docstrings with purpose, params, returns, exceptions, and types
- Write in accessible language that any developer can understand
- Include all important information, but explain complex concepts simply
- Make it immediately understandable without additional research
- When needed, reference related code that provides essential context
- Use concrete examples when helpful

Focus: Formal documentation for functions, classes, and modules that other developers will use.

### Code Comments (Narrative & Defensive)
**Rule: Comments explain the "why" and "what" of complex code logic for maintainers.**

#### Purpose
Code comments significantly reduce mental load when developers quickly read or scan code.
Instead of having to mentally parse and understand complex logic, developers can immediately
grasp the intent from clear narrative comments. This speeds up code comprehension, debugging,
and maintenance.

**AI/LLM Benefit**: Comments and code automatically stay synchronized when using AI models for
refactoring or modifications, as the AI understands both the implementation and the documented
intent.

#### Narrative Comments
- Short "why/what" comment above each logical unit of code
- Use domain terms and explicit states
- Explain business logic and reasoning

#### Defensive Comments
- Use "# Check:" prefix exclusively for validation guards
- Place immediately above the validation check
- Explain what condition is being validated and why it matters

#### Comment Formatting
- Inline comments: 2 spaces before #
- Section comments: Sentence case capitalization

#### Code Reference Formatting
Apply universally to comments, docstrings, and error messages:
- Parameters/attributes/variables: `$parameter_name`
- Functions/methods: `` `function_name` ``

#### Examples

Narrative and defensive comments together:
```python
# Collect fills since last event and net the quantity
fills = broker.get_fills_since(self._last_event_time)
net_qty = sum(f.qty for f in fills)

# Check: ensure we have quantity to trade
if net_qty == 0:
    return

# Send order and record time
broker.submit(Order(instrument, side, net_qty))
self._last_order_time = now()
```

Code references across contexts:
```python
# In comments: "Process $user_input through `validate_data` function"
# In docstrings: "The $timeout parameter controls how long `connect` waits"
# In errors: "Cannot call `start_strategy` because $name is invalid"
```

Focus: Complete internal code commenting strategy with universal formatting standards.

### Exception Messages
Format errors with:
1. Function name in backticks: `` `function_name` ``
2. Variables with `$` prefix: `$market_data_provider`
3. Actual values when helpful: `f"$state ('{self.state}')"`
4. Clear root cause and solution guidance

```python
raise ValueError(
    f"Cannot call `start_strategy` because $state ('{self.state}') is not NEW. "
    f"Call `reset` or create a new Strategy."
)
```

### Import and Package Structure

#### No Re-exports Rule
- Never use re-exports in `__init__.py` files
- Import directly from source modules
- Eliminates ambiguity and ensures consistent imports

```python
# ✅ Good - direct imports
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.domain.market_data.bar.bar import Bar

# ❌ Bad - would require re-exports
from suite_trading import TradingEngine
from suite_trading.domain import Bar
```

#### Package Structure
- Only create `__init__.py` files for executable code (version info, imports)
- Use namespace packages (PEP 420) for organization
- Don't create `__init__.py` files with only docstrings or comments

### Code Organization

#### Regions
Use regions to structure large files/classes:
```python
# region Manage strategies
def add_strategy(self, strategy: Strategy) -> None:
    ...

def remove_strategy(self, name: str) -> None:
    ...
# endregion
```

#### Markdown Formatting
**Rule: All Markdown content must have maximum line length of 100 characters.**

Break lines at natural points (spaces, punctuation) while preserving readability.

## Testing Guidelines
- Don't generate tests unless explicitly asked
- Use pytest (not unittest)
- Test function names: `test_` prefix describing what they test
- Structure: `tests/unit/` and `tests/integration/`
- Mirror package structure being tested
- Keep only root `tests/__init__.py` file

## Git Commit Guidelines
- Write in imperative mood: "Add feature" not "Added feature"
- Subject line ≤ 50 characters, capitalize first word, no period
- Use present tense verbs: Add, Fix, Remove, Update
- Be descriptive about what and why
- Separate body with blank line for longer commits

## Plan and Code Change Visualization

When proposing changes, show per-file Before/After snippets with minimal unique context. Use
fenced code blocks labeled Before/After, keep lines ≤ 100 chars, and include acceptance checks.
Update imports as needed.

Minimal template:

- Step X — Short description

File: path/to/file.py
Context: one-line why

Before:
```python
<minimal unique snippet>
```

After:
```python
<updated minimal unique snippet>
```

Acceptance checks:
- [ ] Concrete, verifiable checks

## Development Status
Early-stage project with core architecture (~60-70%) implemented. Core domain models,
event-driven architecture, and strategy framework are complete. Missing live data providers
and broker integrations.
