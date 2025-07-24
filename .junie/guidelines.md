# Project Overview

Modern algorithmic trading framework in Python for backtesting and live trading.

# Core Development Principles

- **KISS**: Always prefer the simplest working solution
- **YAGNI**: Only implement when actually needed
- **DRY**: Eliminate duplication of information, logic or business rules across the codebase
- **Composition Over Inheritance**: Prefer composition over inheritance hierarchies
- **Fail Fast**: Detect and report errors immediately
- **Intuitive Domain Model**: Create simple, understandable domain models
- **Single Responsibility**: Ensure each class has only one job or responsibility
- **Separation of Concerns**: Organize code so different concerns are handled by different parts of the system
- **Principle of Least Surprise**: Code should behave in ways that users naturally expect

## User-Centric Design Principle

**APIs should be designed for the user, not for internal implementation convenience.**

Guides decisions when there's tension between internal simplicity and external usability. Example: `execution.side` feels natural vs. `execution.order.side` feels awkward.

### Decision Framework

1. **Identify user mental model** - How do users think about this?
2. **Assess implementation cost** - Is the user-friendly approach expensive?
3. **Consider consistency** - Does this fit existing APIs?
4. **Evaluate maintenance** - Will this create ongoing complexity?
5. **Balance principles** - How does this interact with KISS/YAGNI/DRY?

**Rule:** If cost is low and user benefit is clear, favor the user-centric approach.

# Coding Standards

## Naming Conventions

**Rule: All names (functions, variables, classes) should be as simple as possible, predictable, and self-documenting.**

The purpose of any name should be immediately clear and indicate what it does or contains.

### Guidelines

- **Use clear, descriptive names**: Choose names that explain the purpose without needing comments
- **Avoid abbreviations**: Write `user_count` instead of `usr_cnt` or `uc`
- **Use verbs for functions**: Functions should describe what they do (`calculate_total`, `send_message`)
- **Use nouns for variables**: Variables should describe what they contain (`total_amount`, `user_list`)
- **Be specific**: Use `trading_engine` instead of `engine`, `bar_data` instead of `data`
- **Follow conventions**: Use standard Python naming patterns (snake_case for functions/variables)

### Examples

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

## Standard Classes Only

**Rule: Use standard classes exclusively. No dataclasses allowed.**

**Why:** Complete consistency eliminates cognitive overhead and aligns with our core principles:
- **KISS**: One pattern everywhere, zero exceptions to remember
- **Explicit over Implicit**: All initialization and validation logic is clear and visible
- **User-Centric Design**: Predictable, consistent behavior across all domain objects

## Documentation

- Use Google documentation style for all docstrings
- Format docstrings with content on separate lines
- Include purpose, parameters, return values, and exceptions in function docstrings
- Include type information for all parameters, return values, and attributes in docstrings

### Docstring Writing Style

Write docstrings that are easy to understand for everyone:

- **Use natural language**: Write like you're explaining to a colleague, not like a technical manual
- **Use simple words**: Replace complex terms with everyday words that anyone can understand
- **Write for beginners**: Assume the reader is learning - explain concepts clearly and simply
- **Make benefits concrete**: Explain what something does and why it matters in clear, specific terms

**Examples:**
- ✅ "Engine makes sure the provider is available" instead of "Engine validates provider availability"
- ✅ "Simple way to get events from different sources" instead of "Unified interface for event retrieval with permanent closure detection"

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
             order_id: int = None):

# ✅ Good - each parameter on separate line
def __init__(self,
             instrument: Instrument,
             side: OrderDirection,
             quantity: Decimal,
             order_id: int = None):
```

## String Representation Methods

**Rule**: Use `self.__class__.__name__` instead of hardcoded class names in `__str__` and `__repr__` methods.

**Why**: Makes class names automatically update if the class is renamed, improving maintainability.
### Examples

```python
# ❌ Wrong - hardcoded class name
def __str__(self) -> str:
    return f"NewBarEvent(bar={self.bar}, dt_received={self.dt_received})"

# ✅ Good - dynamic class name
def __str__(self) -> str:
    return f"{self.__class__.__name__}(bar={self.bar}, dt_received={self.dt_received})"
```

## Exception Message Formatting

**Rule**: All error and exception messages must follow a specific format to be clear, actionable, and consistent.

### Format Requirements

1. **Function Context**: Always specify which function was called
   - Use backticks around function names: `` `function_name` ``

2. **Variable Identification**: Prefix variables with `$` to distinguish them from normal text
   - Example: `$market_data_provider`, `$trading_engine`, `$bar_type`

3. **Variable Values**: Include actual values of variables when relevant
   - Use f-strings for interpolation: `f"$bar_type ({bar_type})"`
   - For objects, include meaningful identifiers: `f"$instrument ({instrument.symbol})"`

4. **Root Cause**: Clearly state what's None or what condition failed
   - Example: "because $market_data_provider is None"

5. **Solution Guidance**: Provide actionable advice on how to fix the issue
   - Example: "Set a market data provider when creating TradingEngine"

### Examples

```python
# Function call with None check
raise RuntimeError(f"Cannot call `subscribe_to_bars` for $bar_type ({bar_type}) because $market_data_provider is None. Set a market data provider when creating TradingEngine.")

# Value validation
raise ValueError(f"$count must be >= 1, but provided value is: {count}")

# Multiple issues
raise ValueError("User validation failed:\n• $name cannot be empty\n• $age must be at least 18")
```

## Markdown Formatting

**Rule**: All generated Markdown content must have a maximum line length of 100 characters.

**Why**: Consistent line length improves readability and ensures proper formatting across different
editors and viewing environments.

### Requirements

- **Line Length Limit**: No line should exceed 100 characters
- **Automatic Line Breaks**: Add newlines after reaching 100 characters
- **Preserve Readability**: Break lines at natural points (spaces, punctuation) when possible
- **Code Blocks**: Code examples within Markdown should also follow this rule
- **Lists and Headers**: Apply the same 100-character limit to all content types

### Examples

```markdown
# ✅ Good - lines under 100 characters
This is a properly formatted Markdown paragraph that stays within the 100-character limit by
breaking lines at appropriate points to maintain readability and consistency.

# ❌ Bad - line exceeds 100 characters
This is an improperly formatted Markdown paragraph that exceeds the 100-character limit and should be broken into multiple lines for better readability.
```

## Import and Package Structure

### No Re-exports Rule

- **Never use re-exports in `__init__.py` files**
- Each class/function should be imported directly from its source module
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

### Package Structure and `__init__.py` Files

**Rule: Only create `__init__.py` files when they contain executable code.**

Create `__init__.py` files **only** for:
- **Executable code** (imports, variable assignments, function calls)
- **Version information** (root package only: `__version__ = "1.0.0"`)
- **Package initialization logic**

**Don't create** `__init__.py` files that contain only docstrings, comments, or are empty.

Use **namespace packages** (PEP 420) for directory organization - no `__init__.py` needed.

#### Examples

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
