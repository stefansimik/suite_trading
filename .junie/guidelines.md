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

# Coding Standards

## Dataclasses

- Always use `ClassVar` from `typing` module to explicitly mark class variables in dataclasses

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
