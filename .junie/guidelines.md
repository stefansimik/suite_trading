# Project Overview

We are building a modern algorithmic trading framework in Python that allows:
- Backtesting strategies with historical data
- Running live strategies

# Core Development Principles

- **KISS (Keep It Simple, Stupid)**: Always prefer the simplest possible working solution
- **YAGNI (You Aren't Gonna Need It)**: Only implement things when actually needed
- **DRY (Don't Repeat Yourself)**: Every piece of knowledge should have a single representation
- **Composition Over Inheritance**: Prefer composition over inheritance hierarchies
- **Fail Fast**: Detect errors early and report them immediately
- **Intuitive Domain Model**: Create a simple, understandable domain model
- **Broker Agnostic**: Framework should be broker agnostic where possible
- **Single Responsibility Principle (SRP)**: Each class should have only one reason to change and be responsible for one specific functionality
- **Separation of Concerns**: Different aspects of functionality should be handled by different classes, making it crystal clear who is responsible for what

## User-Centric Design Principle

**APIs should be designed for the user, not for internal implementation convenience.**

This principle guides decisions when there's tension between internal code simplicity and external API usability. While KISS and YAGNI promote simplicity, this principle ensures that simplicity doesn't come at the cost of user experience.

Example:
**Domain Model Alignment**: The API should match how users think about the domain
  - `execution.side` feels natural vs. `execution.order.side` feels awkward
  - Users conceptually think "executions have a side" not "executions' orders have a side"

### Decision Framework

When facing API design choices:

1. **Identify the user mental model** - How do users think about this concept?
2. **Assess implementation cost** - Is the user-friendly approach expensive?
3. **Consider consistency** - Does this pattern fit with existing APIs?
4. **Evaluate maintenance** - Will this create ongoing complexity?
5. **Balance principles** - How does this interact with KISS/YAGNI/DRY?

**Rule of thumb:** If the cost is low and the user benefit is clear, favor the user-centric approach.

# Coding Standards

## Dataclasses

- Always use `ClassVar` from `typing` module to explicitly mark class variables in dataclasses

### When to Prefer Normal Classes Over Dataclasses

**Use normal classes instead of dataclasses when:**

- **Logical attribute ordering matters more than technical constraints**
  - When primary identifiers (like `order_id`) should logically come first but have default values
  - When you need to group related attributes together regardless of their default status
  - When dataclass field ordering rules force unnatural domain ordering

- **Complex domain models require flexibility**
  - Core business objects that need sophisticated initialization logic
  - Classes with inheritance hierarchies where constructor flexibility matters
  - When validation logic is complex and benefits from explicit constructor control

**Keep dataclasses for:**
- Simple data containers with natural field ordering
- Immutable value objects (with `frozen=True`)
- Market data structures where technical ordering aligns with logical ordering

**Decision rule:** If natural domain ordering conflicts with dataclass field rules → Use normal classes

## Documentation

- Use Google documentation style for all docstrings
- Format docstrings with content on separate lines
- Include purpose, parameters, return values, and exceptions in function docstrings
- Include type information for all parameters, return values, and attributes in docstrings

## Comment Formatting

- Use consistent indentation for inline comments
- Always use exactly 2 spaces before the `#` symbol for inline comments
- Align all inline comments in the same code block consistently
- Use sentence case for section comments (not title case)

### Example
```python
# Order identification  # ← sentence case for sections
order_id: str  # Unique identifier for the order
side: OrderDirection  # Whether this is a BUY or SELL order
```

## Parameter Formatting

- When functions have many parameters, put each parameter on a separate line for better readability
- This applies to function definitions, method definitions, and class constructors
- Maintain consistent indentation for all parameters

### Examples

```python
# ❌ Wrong - multiple parameters on same line
def __init__(self, instrument: Instrument, side: OrderDirection, quantity: Decimal,
             order_id: int = None, time_in_force: TimeInForce = TimeInForce.GTC,
             filled_quantity: Decimal = Decimal("0")):

# ✅ Good - each parameter on separate line
def __init__(self,
             instrument: Instrument,
             side: OrderDirection,
             quantity: Decimal,
             order_id: int = None,
             time_in_force: TimeInForce = TimeInForce.GTC,
             filled_quantity: Decimal = Decimal("0")):
```

## Exception Message Formatting

- Prefix variables with $ to distinguish them from normal text
- Include actual values of variables in the message
- Use f-strings for string interpolation
- Be specific about requirements and valid ranges

### Examples

```python
# Basic format with variable and its value
if count <= 1:
    raise ValueError(f"$count must be >= 1, but provided value is: {count}")

# Include context and expectations
if start_date >= end_date:
    raise ValueError(f"$start_date ({start_date}) must be earlier than $end_date ({end_date})")

# For multiple issues, use bullet points
def validate_user(user):
    errors = []
    if not user.name:
        errors.append(f"$name cannot be empty, got: '{user.name}'")
    if user.age < 18:
        errors.append(f"$age must be at least 18, got: {user.age}")
    if errors:
        raise ValueError("User validation failed:\n• " + "\n• ".join(errors))
```

## Import and Package Structure

### No Re-exports Rule

- **Never use re-exports in `__init__.py` files**
- Each class/function should be imported directly from its source module
- `__init__.py` files should contain only docstrings explaining the package purpose
- This eliminates import ambiguity and ensures consistent import patterns across the codebase

#### Benefits
- **Zero Ambiguity**: Exactly one way to import each class
- **Clear Dependencies**: Import statements clearly show where each class comes from
- **Zero Maintenance**: No need to maintain `__all__` lists or coordinate exports
- **IDE Friendly**: Auto-completion and "Go to Definition" work perfectly


#### Examples

```python
# ✅ Good - direct imports from source modules
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.order.order_enums import OrderSide

# ❌ Bad - re-exports (not allowed)
from suite_trading import TradingEngine  # Would require re-export
from suite_trading.domain import Bar     # Would require re-export
```

#### Package Structure
- `__init__.py` files contain only:
  - Package docstring explaining the package purpose
  - Version information (only in root `__init__.py`)
  - No imports, no `__all__` lists, no re-exports

# Testing Guidelines

- Don't generate tests unless explicitly asked
- Use `pytest` library (not `unittest`)
- Test function names should start with "test_" and describe what they're testing
- Organize tests in `tests/unit/` and `tests/integration/`
- Mirror the package structure of the code they test
- Keep only the root `tests/__init__.py` file

# Git Commit Guidelines

- Write commits in **imperative mood** (like giving a command)
  - **✅ Good:** "Add user authentication"
  - **❌ Avoid:** "Added user authentication"
- Keep subject line concise (50 chars or less)
- Start with capital letter, no period at end
- Use present tense imperative verbs: Add, Fix, Remove, Update
- Be descriptive about what and why
- For longer commits, add body separated by blank line
