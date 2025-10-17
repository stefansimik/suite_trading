Project: Modern algorithmic trading framework in Python for backtesting and live trading.

# 1. Golden rules and priorities

## 1.1 Core principles
- KISS: Prefer the simplest working solution
- YAGNI: Implement only when needed
- DRY: Do not duplicate information, logic, or business rules
- Fail fast: Detect and report errors immediately
- Intuitive domain model: Keep domain objects simple and understandable
- Single responsibility: Each class has one job
- Separation of concerns: Split responsibilities across the system
- Principle of least surprise: Make behavior match user expectations

## 1.2 Initial development mode
During initial development, backward compatibility is out of scope. Breaking changes are
allowed; remove or redesign anything to get the design right.

## 1.3 User‑centric API design
Rule: Design APIs for the user, not for internal convenience.

Prefer user‑friendly choices when cost is low, they fit the existing style and do not add
ongoing complexity.

# 2. Code writing rules (critical)

## 2.1 Naming
Rule: Names must be simple, predictable, and self‑documenting.

Use clear, descriptive names: verbs for functions, nouns for variables, specific over vague,
and Python snake_case. Avoid abbreviations (e.g., user_count, not usr_cnt).

Examples:
```python
# ✅ Good
def calculate_portfolio_value(positions: list) -> Decimal: ...

# ❌ Bad
def calc_pv(pos: list) -> Decimal: ...
```

### Improving attribute and variable names
- Prefer clear, intuitive, and descriptive names for attributes and variables.
- Keep names concise when possible, but never at the cost of clarity.
- Use domain terms consistently; pick nouns for values and properties, verbs for functions.
- Rename confusing names proactively to reduce reading and maintenance effort.

### Method naming for resource access

- Use `list_*` for methods that return collections (lists, iterables, generators).
  - Examples: `list_active_orders()`, `list_open_positions()`.
- Use `get_*` for methods that return a single resource or value object.
  - Examples: `get_account_info()`, `get_order(order_id)`.
- Use `find_*` or `query_*` only when search/filter semantics are the primary purpose and
  results may be partial or empty from a larger domain. (Optional, future scope.)

## 2.2 Classes, dataclasses, and named tuples
Rule: Use standard classes for fundamental domain models. Dataclasses and named tuples are
allowed for simple config or helper/value objects only.


## 2.3 Parameter formatting
For long signatures, put one parameter per line, consistent indent, trailing comma.

Example:
```python
def __init__(
    self,
    instrument: Instrument,
    side: OrderDirection,
    quantity: Decimal,
    order_id: int | None = None,
) -> None: ...
```

## 2.4 Logging rules (project‑wide)
Rule: Logs must be precise, consistent, and easy to scan. Use f‑strings everywhere.

Always use f‑strings
- Applies to logs, exceptions, messages, and general strings.
- Never use logger format args or str.format/percent formatting.

Allowed:
- `logger.info(f"Started Strategy named '{name}'")`
- Plain constant strings when no interpolation is needed

Forbidden:
- `logger.info("Started Strategy '%s'", name)`
- `logger.info("Started Strategy '{}'".format(name))`
- `"Hello, %s" % name`

Identify domain objects in logging messages:
- When referring to Strategies and EventFeeds, use this type of message:
  - "Strategy named '{strategy_name}'", "EventFeed named '{feed_name}'".
- When referring to the concept/type only: use the capitalized class name.
  - Examples: Strategy, EventFeed, Broker, EventFeedProvider.
- When you must include the class of an instance, make it explicit: "(class {obj.__class__.__name__})".

Pluralization of class concepts
- Use capitalized class with (s) as needed when referring to counts: "EventFeed(s)",
  "Strategy(ies)", "broker(s)" only if not a class concept.

Message structure
- Prefer the pattern: "<Verb> <ClassName> named '{name}' <short context>".
  - Example: `logger.info(f"Added EventFeed named '{feed_name}' to Strategy named '{s_name}'")`
- For state transitions: "ClassName named '{name}' transitioned to <STATE>".
- For errors: start with action/context, then the object, then the error.
  - Example: `logger.error(f"Error closing EventFeed named '{name}': {e}")`

Capitalization and terminology
- Capitalize domain class names (Strategy, EventFeed, Broker, EventFeedProvider) when used as nouns.
- Use "event-feed" (hyphenated) for generic prose; use "EventFeed" when referring to the class.

One‑line rule for all logger calls
- All logger calls must be on a **single line**, regardless of message length.
- Do not wrap logger calls; a logger call must be one line even if >100 chars.

Wrong:
```python
logger.debug(
    f"EventFeed named '{feed_name}' for Strategy named '{strategy_name}' was already finished",
)
```

Correct:
```python
logger.debug(f"EventFeed named '{feed_name}' for Strategy named '{strategy_name}' was already finished")
```

Examples (Do/Don't)
- Do: `logger.info(f"Started Strategy named '{name}'")`
- Do: `logger.error(f"Error auto-stopping Strategy named '{name}': {e}")`
- Do: `logger.debug(f"Cleaned up finished EventFeed named '{feed_name}' for Strategy named '{s}'")`
- Don't: `logger.info(f"Started strategy '{name}'")`  # wrong casing/pattern
- Don't: `logger.debug("EventFeed '%s' removed", feed_name)`  # can use only f-strings

## 2.5 String representation methods
Rule: Use `self.__class__.__name__` in `__str__` and `__repr__`.

Example:
```python
# ❌ Wrong
def __str__(self) -> str:
    return f"NewBarEvent(bar={self.bar}, dt_received={self.dt_received})"

# ✅ Good
def __str__(self) -> str:
    return f"{self.__class__.__name__}(bar={self.bar}, dt_received={self.dt_received})"
```

## 2.6 Docstrings (API Documentation)
**Rule: Docstrings document public APIs for external developers using your code.**

Key requirement for docstrings:
- Use Google-style docstrings with purpose, params, returns, exceptions, and types
- Write in accessible language that ANY developer can understand
- Include all important information, but explain complex concepts simply
- Make it immediately understandable without additional research
- When needed, reference related code that provides essential context
- Use concrete examples when helpful
.

## 2.7 Code Comments
**Rule: Comments explain the "why" and "what" of complex code logic for maintainers.**

### Purpose
Code comments significantly reduce mental load when developers quickly read or scan code.
Instead of having to mentally parse and understand complex logic, developers can immediately grasp the intent from clear narrative comments.
This speeds up code comprehension, debugging, and maintenance.

**AI/LLM Benefit**: Comments and code automatically stay synchronized when using AI models for refactoring or modifications,
as the AI understands both the implementation and the documented intent.

### Narrative Comments
- Short "why/what" comment above each logical unit of code
- Use domain terms and explicit states
- Explain business logic and reasoning

### Defensive Comments
- Use "# Check:" prefix exclusively for validation guards
- Place immediately above the validation check
- Explain what condition is being validated and why it matters

### Comment Formatting
- Inline comments: 2 spaces before #
- Section comments: Sentence case capitalization

### Code Reference Formatting
Apply universally to comments, docstrings, and error messages:
- Parameters/attributes/variables: `$parameter_name`
- Functions/methods: `` `function_name` ``

### Examples

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

## 2.8 Exception messages
Exception messages checklist:
- 100% clear, use project terms, guide the fix.
- Include function name in backticks.
- Identify variables with $ and real names; include values when helpful.
- Message inside Exception must be on a **single line**, regardless of message length.
- Do not wrap message in exception ; message must be one line even if >999 chars.

Template:
```python
raise ValueError(f"Cannot call `start_strategy` because $state ('{self.state}') is not NEW. Call `reset` or create a new Strategy.")
```

## 2.9 Markdown formatting
Keep all Markdown lines (including code) <= 100 chars. Break lines at natural points.

## 2.10 Datetime formatting in `__str__` and `__repr__`
Rule: If an object includes datetimes in its string representations, they must be formatted with utilities from `suite_trading.utils.datetime_utils`.

Why:
- Consistency across the codebase
- Predictable, human-readable output
- Avoids ad-hoc or locale-dependent formatting

Requirements:
- Use `format_dt(dt)` for a single timestamp
- Use `format_range(start_dt, end_dt)` for intervals

Canonical example:
- `Bar.__str__` uses `format_range(start_dt, end_dt)` correctly
- `Bar.__repr__` is updated to use the same utility for datetimes

Examples:
```python
# Single timestamp
return f"{self.__class__.__name__}(id={self.id}, at={format_dt(self.timestamp)})"

# Range
dt_str = format_range(self.start_dt, self.end_dt)
return f"{self.__class__.__name__}({self.kind}, {dt_str})"
```

## 2.11 Typing: always enable postponed annotations

Rule: Start every first‑party module with `from __future__ import annotations`. Use direct type
names everywhere (no quotes) — including self‑references in the same module/class/Protocol.
Never use string module paths (e.g., "a.b.Type"); import the type.

Imports for types:
- Prefer unconditional imports unless they cause cycles or are heavy.
- Otherwise import under `if TYPE_CHECKING:` and still use direct names (unquoted).
- If using `typing.get_type_hints` at runtime, ensure symbols exist at runtime or pass
  `globalns`/`localns`.

Annotation style:
- Builtin generics: `list[T]`, `dict[K, V]`, `set[T]`, `tuple[...]`.
- Use `|` (and `| None`) instead of `Union`/`Optional`.
- Use `type[T]` for class objects.
- `Callable[[...], R]` with explicit return type.

Example:
```python
class Broker(Protocol):
    def set_callbacks(
        self,
        on_execution: Callable[[Broker, Order, Execution], None],
        on_order_updated: Callable[[Broker, Order], None],
    ) -> None: ...

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from suite_trading.domain.order.execution import Execution

self._on_execution: Callable[[Broker, Order, Execution], None] | None = None
```

Acceptance checks:
- [ ] Module starts with `from __future__ import annotations`.
- [ ] No quoted forward references (methods, attributes, Protocols, Callables).
- [ ] Builtin generics only (no `typing.List`/`typing.Dict`).
- [ ] `|` unions and `| None` (no `Union`/`Optional`).
- [ ] `Callable[[...], R]` list form with explicit return type.
- [ ] Cross‑module types imported unconditionally or under `TYPE_CHECKING`.
- [ ] If `get_type_hints` is used at runtime, symbols resolvable or namespaces provided.

## 2.12 __slots__ for high-volume, fixed-shape classes

Rule: For classes with many instances (e.g., market data, events), define `__slots__` to reduce
memory use, improve attribute access speed, and prevent accidental attributes.

When to use:
- High instance counts at runtime (Bars, TradeTicks, QuoteTicks, PriceSample, Event subclasses).
- Fixed attribute schema; no dynamic attributes required.
- No reliance on an instance `__dict__`.

Inheritance requirement:
- If a parent class defines `__slots__`, every subclass must also define `__slots__`.
  - Use `__slots__ = ()` when the subclass adds no new instance fields.
  - Otherwise list the private attribute names actually assigned (e.g., `"_price"`).

Implementation tips:
- Slot the private underscored names used in `__init__`.
- Do not add `"__weakref__"` unless instances are weak-referenced.
- If a subclass truly needs dynamic attributes, include `"__dict__"` in its `__slots__`.

Examples:
```python
class Event:
    __slots__ = ("_dt_event", "_dt_received")

class BarEvent(Event):
    __slots__ = ()  # no new instance fields

class QuoteTick(Event):
    __slots__ = (
        "_instrument",
        "_bid_price",
        "_ask_price",
        "_bid_volume",
        "_ask_volume",
        "_timestamp",
    )
```

## 2.13 Comparison and sorting (total ordering)

Rule: For any custom comparable type, implement full ordering with `@total_ordering`.

Requirements:
- Implement `__lt__` and ensure `__eq__` is defined. For Enum types, `Enum.__eq__` is enough.
- If $other is a different type, return `NotImplemented` from the comparison methods.
- Put ordering in one place (a precedence map or a key function); do not duplicate logic.
- Annotate returns as `bool | NotImplementedType`.
- Keep methods short and readable. Follow 2.1 naming and 2.11 typing.

Example (current `PriceType` implementation):
```python
from __future__ import annotations
from enum import Enum
from functools import total_ordering
from types import NotImplementedType

@total_ordering
class PriceType(Enum):
    BID = "BID"
    ASK = "ASK"
    MID = "MID"
    LAST_TRADE = "LAST_TRADE"

    def __lt__(self, other: object) -> bool | NotImplementedType:
        if not isinstance(other, PriceType):
            return NotImplemented
        return _PRICE_TYPE_ORDER[self] < _PRICE_TYPE_ORDER[other]

# Single source of truth for ordering: defined once and reused
_PRICE_TYPE_ORDER = {
    PriceType.BID: 0,
    PriceType.ASK: 1,
    PriceType.MID: 2,
    PriceType.LAST_TRADE: 3,
}
```

Notes:
- `__eq__` is provided by `Enum` (identity comparison), which satisfies `@total_ordering`.

Why `NotImplemented`?
- It enables Python's reflected operations and correct type dispatch during comparisons.

Acceptance checks:
- [ ] Class is decorated with `@total_ordering`.
- [ ] `__lt__` returns `NotImplemented` when $other is not the same type.
- [ ] Ordering uses a single precedence map/key defined once (not recreated per call).
- [ ] Return type hints include `NotImplementedType`.
- [ ] Module starts with `from __future__ import annotations`.
- [ ] If using `Enum`, relying on its `__eq__` is acceptable; otherwise implement `__eq__`.

# 3. Code organization (supporting)

## 3.1 Regions
Improve code regions to present structure clearly and simply.

Guidelines:
- Add short, meaningful regions adapted to each file/class.
- Suggested generic regions (use when relevant):
  - Init — constructors/initialization
  - Main — main functionality/public API
  - Utilities (or Convenience) — helper functions for comfort operations
  - Internal — internal/private methods not part of public API
  - Properties — public properties
  - Magic — magic methods like __str__, __repr__, etc.
- You may introduce new, appropriate region names when they create cohesive units of functionality.
- Not all regions must be used; include only those that make sense for the file.
- Always mark regions with "# region NAME" and "# endregion".
- Spacing: keep one empty line after "# region NAME" and one empty line before "# endregion".
- Remove all empty regions.
- Order functions within a region in a meaningful way: more important first, less important later.

## 3.2 Imports and package structure

Import directly from source modules; never re‑export in __init__.py. After changes, remove
unused imports and add missing ones. Prefer namespace packages; only create __init__.py for
executable code (e.g., __version__).

# 4. Testing guidelines
- Do not generate tests unless explicitly asked
- Use pytest (not unittest)
- Test function names start with `test_` and describe what they test
- Organize tests in `tests/unit/` and `tests/integration/`
- Mirror the package structure of the code under test
- Keep only the root `tests/__init__.py` file

# 5. Git commit guidelines
- Never auto-commit: Junie must not create commits, tags, or pushes unless explicitly requested
  by the User in the current message.
- Write commits in imperative mood (command form)
  - ✅ "Add user authentication"; ❌ "Added user authentication"
- Subject line: <= 50 chars; start with a capital letter; no period at end
- Use present tense imperative verbs: Add, Fix, Remove, Update
- Be descriptive about what and why
- For longer commits, add a body separated by a blank line

# 6. Plan and code change visualization
When proposing changes, show per‑file Before/After snippets with minimal unique context. Use
fenced code blocks labeled Before/After, keep lines <= 100 chars, and include acceptance
checks. Update imports as needed.

Minimal template:

- Step X — Short description

File: path/to/file.py
Context: one‑line why

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
