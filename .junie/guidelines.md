# Project Overview

Modern algorithmic trading framework in Python for backtesting and live trading.

# Core Development Principles

- **KISS**: Always prefer the simplest working solution
- **YAGNI**: Only implement when actually needed
- **DRY**: Eliminate duplication of information, logic or business rules across the codebase
- **Fail Fast**: Detect and report errors immediately
- **Intuitive Domain Model**: Create simple, understandable domain models
- **Single Responsibility**: Ensure each class has only one job or responsibility
- **Separation of Concerns**: Organize code so different concerns are handled by different parts of the system
- **Principle of Least Surprise**: Code should behave in ways that users naturally expect

## Initial Development Mode

**Rule: During initial development, all code changes can ignore historical compatibility and backwards compatibility.**

**Why:** We are in the initial development phase of the library where rapid iteration and improvement are prioritized over stability. This means:

- **Any functionality can be removed** and replaced with new improved implementations
- **Breaking changes are allowed** without deprecation warnings or migration paths
- **APIs can be redesigned** to better serve user needs without maintaining old interfaces
- **No backwards compatibility guarantees** - the result does not have to be backwards compatible
- **Focus on getting it right** rather than maintaining legacy code that doesn't serve the current vision

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
- Add a trailing comma after the last parameter in multi-line parameter lists
- For long function names, use proper spacing and alignment

### Examples

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
    until_dt: Optional[datetime] = None,
) -> Sequence[Bar]:
    ...
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

## String interpolation and logging formatting

**Rule: Always use f-strings. Never use old-style interpolation or logger format args.**
- This rule applies everywhere: logs, exceptions, messages and general strings.

### Allowed
- f-strings: `logger.info(f"Started strategy '{name}'")`
- Plain constant strings when no interpolation is needed

### Forbidden
- `logger.info("Started strategy '%s'", name)`
- `logger.info("Started strategy '{}'".format(name))`
- `"Hello, %s" % name`



## Exception Message Formatting

**Rule**: All error and exception messages must be 100% clear, understandable, and fully in sync with terminology used in the codebase.

**Why**: Exception messages are critical user-facing communication that must be immediately clear about what went wrong and how to fix it. Unclear or inconsistent terminology creates confusion and poor user experience.

### Core Principles

1. **100% Clarity**: Messages must be instantly understandable without ambiguity
2. **Terminology Consistency**: Use exact same terms as the codebase (e.g., "added to TradingEngine" not "registered")
3. **Specific Variable Types**: Always specify what type of variable (e.g., "strategy name" not just "name")

### Format Requirements

1. **Function Context**: Always specify which function was called
   - Use backticks around function names: `` `function_name` ``

2. **Variable Identification**: Prefix variables with `$` and use actual variable names from the code
   - **CRITICAL RULE**: `$variable_name` must represent actual variables/functions/references in the code
   - ❌ Bad: `$execution_order_id` when the actual code is `execution.order.id`
   - ✅ Good: `$order_id` (matches the actual variable name)
   - ❌ Bad: `$self_id` when the actual code is `self.id`
   - ✅ Good: `$id` (matches the actual variable name)
   - ❌ Bad: `$trading_engine_instance` when variable is `self._trading_engine`
   - ✅ Good: `$_trading_engine` (matches the actual variable name)
   - ❌ Bad: `$strategy_state` when variable is `self.state`
   - ✅ Good: `$state` (matches the actual variable name)

3. **Variable Values**: Include actual values of variables when relevant
   - Use f-strings for interpolation: `f"$strategy_name ('{name}')"`
   - For objects, include meaningful identifiers: `f"$instrument ({instrument.symbol})"`

4. **Root Cause**: Clearly state what condition failed using codebase terminology
   - ✅ Good: "because strategy name $name ('test') is not added to this TradingEngine"
   - ❌ Bad: "because $name is not registered" (unclear terminology)

5. **Solution Guidance**: Provide actionable advice with specific method names
   - ✅ Good: "Add the strategy using `add_strategy` first"
   - ❌ Bad: "Register the strategy first" (inconsistent terminology)

### Examples

```python
# Clear variable type specification and consistent terminology
raise KeyError(
    f"Cannot call `start_strategy` because strategy name $name ('{name}') is not added to this TradingEngine. Add the strategy using `add_strategy` first."
)

# Provider-specific clear messaging
raise ValueError(
    f"EventFeedProvider with provider name $name ('{name}') is already added to this TradingEngine. Choose a different name."
)

# Value validation with clear context
raise ValueError(f"$quantity must be >= 1, but provided value is: {quantity}")

# Multiple issues with clear specification
raise ValueError(
    "Strategy validation failed:\n"
    "• $strategy_name cannot be empty\n"
    "• $strategy must be in NEW state"
)
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

## Code Organization with Regions

**Rule**: Use regions to organize code when files become larger and contain multiple logical sections.

**Why**: Regions make code more structured and intuitive, especially for AI-generated/edited files. They provide clear visual separation of different concerns and make navigation easier.

### When to Use Regions

- **Files with 100+ lines** that contain multiple logical sections
- **Classes with multiple responsibilities** (engines, strategies, factories)
- **Files with distinct functional groups** (initialization, lifecycle, data handling, etc.)

### Region Guidelines

- **Use simple, intuitive names**: Prefer "Initialize engine" over "Initialization Methods"
- **Use verbs for actions**: "Start and stop engine", "Manage strategies", "Submit orders"
- **Group related functionality**: Place management regions together (strategies, providers, brokers)
- **Consistent formatting**: Always use `# region [name]` and `# endregion` markers
- **Re-evaluate when editing**: Update regions when making changes to maintain organization

### Examples

```python
class TradingEngine:
    # region Initialize engine
    def __init__(self):
        # Initialization code
        pass
    # endregion

    # region Start and stop engine
    def start(self):
        pass

    def stop(self):
        pass
    # endregion

    # region Manage strategies
    def add_strategy(self, strategy):
        pass

    def remove_strategy(self, strategy):
        pass
    # endregion
```

## Import and Package Structure

### Import Management After Code Changes

**Rule: After each code change, imports must be re-checked to remove obsolete imports and add missing imports.**

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

## Defensive Checks Comments

Rule: Put one concise comment immediately before every defensive check.
It must start with "# Check:".

What counts: Guards that validate input, state, existence, None, or configuration.
Includes try/except used only for validation and asserts used as runtime guards.

Style
- Start with "# Check:"
- Be specific (<= 100 chars)
- Use imperative phrasing ("quantity must be positive")
- Place it right before the check
- One line per independent check

Example
```python
# Check: strategy must be registered
if name not in self._strategies:
    raise KeyError(
        f"Cannot call `start_strategy` because $name ('{name}') is not registered.",
    )
```

Where to apply
- Constructors and validators (__init__, _validate, property setters)
- Orchestration (engine/strategy/provider/broker)
- Parsing and conversion
- Any fast-fail function

Why: Makes intent obvious, supports Fail Fast and keeps reviews unambiguous.

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


# Plan and code change visualization

**Rule**: All plans and proposed code changes must be shown with clearly formatted
Before/After code sections so users can quickly see what will change.

**Why**: Visual diffs reduce ambiguity, speed up reviews, and make intent obvious.

## Before/After visualization rules

For every file and code location you plan to change, include:
1) A file header line on its own line:
   - File: path/to/file.py
2) A short one-line context sentence (optional but recommended).
3) A Before code block with the closest minimal, unique snippet.
4) An After code block with the exact new snippet.

Formatting rules:
- Use fenced code blocks. Prefer the correct language hint (python, text).
- Precede each code block with a plain text label: "Before:" or "After:".
- Keep each snippet concise but uniquely identifiable in the file.
- Wrap lines at <= 100 chars (see Markdown Formatting rules).
- If showing imports or docstrings, include only the necessary surrounding lines.
- If the change is a deletion only, show Before and a note: "After: (removed)".
- If the change is an addition only, show Before with closest anchor context, then After with
  the added block; if no stable anchor exists, clearly state the insertion point
  (e.g., "After line: 'class TradingEngine:'").

## Logging and comments

- When logs are affected, show Before/After snippets for the log lines too.
- When comments or docstrings change, include them in the snippets.
- Respect Comment Formatting and Docstring Writing Style rules.
=

## Minimal template you must follow

Use this template when presenting a plan that changes code. Keep blocks short and unique.

- Step X — Short description

File: <full/path/to/file.py>
Context: <what and why in one sentence>

Before:
```python
<minimal unique snippet>
```

After:
```python
<updated minimal unique snippet>
```

Acceptance checks:
- [ ] List concrete, verifiable checks relevant to this file/change

Repeat the File/Before/After pattern for each touched file. Keep each code block under
100 chars per line. Ensure imports are updated after changes.
