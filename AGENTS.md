# Modern Algorithmic Trading Framework - Development Guidelines

**Project**: Python framework for backtesting and live trading.

---

# 1. Core Principles & Development Philosophy

## 1.1. Design Principles
- **KISS (Keep It Simple, Stupid):** Simplest working solution
- **YAGNI (You Aren't Gonna Need It):** Implement only when actively required
- **DRY (Don't Repeat Yourself):** No duplication of information, logic, or business rules
- **Fail Fast:** Report errors immediately upon detection
- **Intuitive Domain Model:** Keep objects simple; names/flows match trading mental model
- **Single Responsibility:** Each class has one distinct purpose
- **Separation of Concerns:** Divide responsibilities into distinct sections
- **Principle of Least Surprise:** Behavior aligns with user expectations
- **User-Centric API:** Design for users, not internal convenience

## 1.2. Development Mode
**Breaking changes allowed** during initial development. Backward compatibility is out of scope.
Remove or redesign anything to achieve optimal design.

**Acceptance checks:**
- [ ] Rules reflected in new modules; reviews mention them explicitly
- [ ] Acronyms defined inline on first use (KISS, YAGNI, DRY)

---

# 2. Naming Conventions & API Design

## 2.1. General Naming Rules
Names must be **simple, predictable, and self-documenting**. Use Python `snake_case`.
Avoid abbreviations.

- **Functions/Methods:** Use verbs describing the action
- **Variables/Attributes:** Use nouns describing the data
- **Domain terms:** Use consistently; be concise but never sacrifice clarity

## 2.2. Method Naming Patterns

**Resource access and retrieval:**
- `list_*`: Return collections
  - Example: `list_active_orders()`, `list_open_positions()`
- `get_*`: Retrieve existing single resource; **cheap, no modeling, no heavy computation**
  - Example: `get_account_info()`, `get_order(order_id)`, `get_best_bid()`
- `build_*` or `create_*`: Construct/model new objects from inputs (signals expensive operation)
  - Example: `build_order_book(sample)`, `create_snapshot(now)`, `build_position_report()`
- `compute_*`: Derived numeric metrics requiring calculation
  - Example: `compute_realized_pnl(trades)`, `compute_sharpe(returns)`
- `find_*` or `query_*`: Search/filter with partial/empty results (optional, future scope)

**Critical rule:** ❌ **Never use `get_*` for modeling or heavy computation**

**Examples:**
```python
# ✅ Good
def calculate_portfolio_value(positions: list) -> Decimal: ...
def build_order_book(sample: MarketData) -> OrderBook: ...

# ❌ Bad
def calc_pv(pos: list) -> Decimal: ...
def get_order_book(sample: MarketData) -> OrderBook: ...  # Should be build_*
```

**Acceptance checks:**
- [ ] Public APIs use verbs above consistently
- [ ] No `get_*` performs modeling or heavy calculations

---

# 3. Type Annotations & Signatures

## 3.1. Modern Typing Rules
**Always start modules with:** `from __future__ import annotations`

**Required practices:**
- Use direct type names (no quotes, no `"a.b.Type"` strings)
- Builtin generics only: `list[T]`, `dict[K, V]`, `set[T]`, `tuple[...]`
- Use `|` and `| None` instead of `Union`/`Optional`
- Use `type[T]` for class objects
- `Callable[[...], R]` with explicit return type
- Import cross-module types unconditionally or under `if TYPE_CHECKING:`

**Example:**
```python
from __future__ import annotations
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from suite_trading.domain.order.execution import Execution

class Broker(Protocol):
    def set_callbacks(
        self,
        on_execution: Callable[[Broker, Order, Execution], None],
        on_order_updated: Callable[[Broker, Order], None],
    ) -> None: ...
```

## 3.2. Parameter Formatting
Long signatures: **one parameter per line**, consistent indent, **trailing comma**.

```python
def __init__(
    self,
    instrument: Instrument,
    quantity: Decimal,
    order_id: int | None = None,
) -> None: ...
```

**Acceptance checks:**
- [ ] Module starts with `from __future__ import annotations`
- [ ] No quoted forward references
- [ ] Only builtin generics used (no `typing.List`/`Dict`)
- [ ] `|` unions and `| None` (no `Union`/`Optional`)
- [ ] `Callable[[...], R]` style with explicit return type
- [ ] Types imported properly; `get_type_hints` resolvable

---

# 4. Documentation, Comments & Messaging

This section covers all developer-facing text: docstrings, comments, logs, and exceptions.

## 4.1. Docstrings (Public API Documentation)

**Purpose:** Document public APIs for external developers.

**Requirements:**
- Google-style format: purpose, params, returns, exceptions, types
- **Simple, conversational English** - avoid dense jargon
- Include all important information; explain complex concepts simply
- Make immediately understandable without research
- Use concrete examples when helpful

**Example:**
```python
def calculate_portfolio_value(positions: list) -> Decimal:
    """Calculates the total value of all positions in a portfolio.

    This sums the market value of each position based on current prices.
    Positions with zero quantity are excluded from the calculation.

    Args:
        positions: List of Position objects with instrument and quantity.

    Returns:
        Total portfolio value as a Decimal.

    Raises:
        ValueError: If any position has invalid price data.
    """
    ...
```

## 4.2. Code Comments (Internal Documentation)

**Purpose:** Explain "why" and "what" of complex logic for maintainers. Reduces mental load
and makes AI-assisted refactoring safer.

### Narrative Comments
- Short "why/what" comment above each logical unit
- Use domain terms and explicit states
- Explain business logic and reasoning
- Simple, conversational English

### Defensive Comments
- Use **`# Check:`** prefix exclusively for validation guards
- Place **immediately above** validation check
- Explain what condition is validated and why it matters

### Code Reference Formatting
Apply to comments, docstrings, and error messages:
- **Parameters/attributes/variables:** `$parameter_name`
- **Functions/methods:** `` `function_name` ``

**Example:**
```python
# Collect fills since last event and net the quantity
fills = broker.get_fills_since(self._last_event_time)
net_qty = sum(f.qty for f in fills)

# Check: ensure we have quantity to trade before submitting order
if net_qty == 0:
    return

# Send order and record submission time
broker.submit(Order(instrument, side, net_qty))
self._last_order_time = now()
```

**Acceptance checks:**
- [ ] `# Check:` used only for validation guards
- [ ] Placed immediately above guard
- [ ] Code reference formatting followed (`$var`, `` `func` ``)

## 4.3. Logging

**Core rules:** Logs must be **precise, consistent, easy to scan**.

### Formatting Requirements
- ✅ **Always use f-strings** for interpolation
- ❌ **Never use** logger format args: `logger.info("msg %s", var)`
- ❌ **Never use** `.format()`: `"msg {}".format(var)`
- ❌ **Never use** `%` formatting: `"msg %s" % var`

### **CRITICAL: One-Line Rule**
**Every logger call must be a single line**, even if >100 chars. Do not wrap logger calls.

```python
# ❌ WRONG - Wrapped logger call
logger.debug(
    f"EventFeed named '{feed_name}' was already finished",
)

# ✅ CORRECT - Single line
logger.debug(f"EventFeed named '{feed_name}' for Strategy named '{strategy_name}' was already finished")
```

### Domain Object Identification
- Strategies/EventFeeds: `"Strategy named '{strategy_name}'"`, `"EventFeed named '{feed_name}'"`
- Concept/type only: use capitalized class name (`Strategy`, `EventFeed`, `Broker`)
- Include instance class: `"(class {obj.__class__.__name__})"`

### Message Structure
- Pattern: `"<Verb> <ClassName> named '{name}' <short context>"`
- State transitions: `"ClassName named '{name}' transitioned to <STATE>"`
- Errors: action/context → object → error

### Capitalization & Terminology
- Capitalize domain class names when used as nouns
- Use "event-feed" (hyphenated) for generic prose
- Use `EventFeed` when referring to the class
- Pluralization: "EventFeed(s)", "Strategy(ies)", "broker(s)"

**Examples:**
```python
# ✅ Good
logger.info(f"Started Strategy named '{strategy_name}'")
logger.debug(f"EventFeed named '{feed_name}' was already finished")
logger.error(f"Error closing EventFeed named '{feed_name}': {e}")

# ❌ Bad - using format args
logger.info("Started Strategy '%s'", strategy_name)

# ❌ Bad - wrapped across lines
logger.debug(
    f"EventFeed named '{feed_name}' was already finished",
)
```

**Acceptance checks:**
- [ ] All logger/exception strings use f-strings (no %, .format, or logger args)
- [ ] No wrapped logger calls; each is one line
- [ ] Messages use naming/structure rules above

## 4.4. Exception Messages

**Requirements:**
- 100% clear, use project terms, guide the fix
- Include function name in backticks: `` `function_name` ``
- Identify variables with `$` and real names; include values when helpful
- **Message must be single line**, regardless of length

**Template:**
```python
raise ValueError(
    f"Cannot call `start_strategy` because $state ('{self.state}') is not NEW. "
    f"Call `reset` or create a new Strategy."
)
```

**Example:**
```python
raise ValueError(
    f"Cannot submit Order with $quantity ({quantity}) <= 0. "
    f"Provide a positive quantity or call `cancel_order` instead."
)
```

---

# 5. Class Design & Structure

## 5.1. Class Usage Guidelines
- **Standard Classes:** Use for fundamental domain models
- **Dataclasses/NamedTuples:** Only for simple config or value objects

## 5.2. String Representation (`__str__`, `__repr__`)

**Always include** `self.__class__.__name__` to make object types clear.

**Datetime formatting:** Use utilities from `suite_trading.utils.datetime_utils`:
- `format_dt(dt)` for single timestamp
- `format_range(start_dt, end_dt)` for intervals

**Examples:**
```python
# ✅ Good - using class name and datetime utils
def __str__(self) -> str:
    return f"{self.__class__.__name__}(id={self.id}, at={format_dt(self.timestamp)})"

def __str__(self) -> str:
    dt_str = format_range(self.start_dt, self.end_dt)
    return f"{self.__class__.__name__}(kind={self.kind}, range={dt_str})"

# ❌ Bad - hardcoded class name
def __str__(self) -> str:
    return f"BarEvent(bar={self.bar})"
```

**Acceptance checks:**
- [ ] `__str__`/`__repr__` use `self.__class__.__name__`
- [ ] Datetime utils used for timestamp formatting

## 5.3. Memory Optimization (`__slots__`)

**Use for:** Classes with high instance counts (Bars, Ticks, Events) to reduce memory and
improve speed.

**When to use:**
- High instance counts at runtime
- Fixed attribute schema
- No reliance on instance `__dict__`

### **Critical Inheritance Rule**
**If parent defines `__slots__`, every subclass MUST define `__slots__` too:**
- Use `__slots__ = ()` when subclass adds no new fields
- Otherwise list private attribute names used in `__init__` (e.g., `"_price"`)
- Do not add `"__weakref__"` unless needed
- Include `"__dict__"` only when dynamic attrs required

**Example:**
```python
class Event:
    __slots__ = ("_dt_event", "_dt_received")

class BarEvent(Event):
    __slots__ = ()  # No new instance fields

class QuoteTick(Event):
    __slots__ = ("_instrument", "_bid_price", "_ask_price", "_timestamp")
```

**Acceptance checks:**
- [ ] `__slots__` defined for high-volume classes
- [ ] Subclasses of slotted classes define `__slots__` (use `()` when none)

## 5.4. Comparison & Sorting (`@total_ordering`)

**For any custom comparable type:** Implement full ordering with `@total_ordering`.

**Requirements:**
- Implement `__lt__` and ensure `__eq__` is defined
- Return `NotImplemented` for different types
- Single source of truth for ordering (precedence map/key function)
- Annotate returns as `bool | NotImplementedType`

**Example:**
```python
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

_PRICE_TYPE_ORDER = {
    PriceType.BID: 0,
    PriceType.ASK: 1,
    PriceType.MID: 2,
    PriceType.LAST_TRADE: 3,
}
```

**Acceptance checks:**
- [ ] Class decorated with `@total_ordering`
- [ ] `__lt__` returns `NotImplemented` for different types
- [ ] Single precedence map defined once
- [ ] Return type hints include `NotImplementedType`
- [ ] Module starts with `from __future__ import annotations`

---

# 6. Complexity Control & Premature Abstraction

**Core rule:** Do not introduce new types, layers, helpers, or indirection unless gain is
immediate, material, well-justified, and documented.

## 6.1. What This Means Now
- ❌ **Don't alias simple primitives:** `Price = Decimal`, `Volume = Decimal`
- ✅ **Use explicit types:** `tuple[Decimal, Decimal]`
- ❌ **Don't add wrapper classes** for tuples/lists/dicts just to name fields

**Preferred:**
```python
bids: Sequence[tuple[Decimal, Decimal]]
```

## 6.2. When to Add New Value Object

**At least ONE must be true:**
- Must enforce invariants/units/validation (currency, tick size, rounding)
- Attach behavior with data (methods, arithmetic with rounding rules)
- Measurable performance/memory improvements in hot paths
- Reused across **3+ call sites/modules** with real maintenance cost
- Represents external boundary (serialization schema, protocol, storage)

## 6.3. If Adding One
- Prefer `NamedTuple` for read-only shapes
- Or `@dataclass(frozen=True)` with `__slots__` when validation needed
- Include **`# Justification: <reason>`** comment above definition
- State invariant(s) or performance reason in docstring

**Example:**
```python
# Justification: Enforce non-negative volume and unify schema across 5 modules
class BookLevel(NamedTuple):
    """Represents a single price level in an order book.

    Invariants:
        - volume must be non-negative
        - price must be valid Decimal
    """
    price: Decimal
    volume: Decimal

    def __post_init__(self):
        if self.volume < 0:
            raise ValueError(f"Volume must be non-negative, got {self.volume}")
```

**Acceptance checks:**
- [ ] No primitive aliases exposed in public APIs
- [ ] New abstractions include `# Justification:` line
- [ ] Signatures use explicit types unless justified value object exists
- [ ] Utils/wrappers only with 3+ reuse sites or explicit hot-path perf need

---

# 7. Domain-Specific Rules

## 7.1. Price Validation
**Negative prices are allowed** when market supports them. Do not reject negative `$price`
values in generic validation.

**Why:** Certain markets (electricity, power futures, interest rate instruments) may have
negative prices.

**Acceptance checks:**
- [ ] Generic validators allow negative prices where market supports them

---

# 8. Code Organization

## 8.1. Regions
Use `# region NAME` and `# endregion` to group related blocks. Use sparingly; not for tiny
items.

**Suggested regions (use when relevant):**
- **Init:** Constructors/initialization
- **Main:** Main functionality/public API
- **Properties:** Public properties
- **Utilities** or **Convenience:** Helper functions
- **Orders:** Order management and routing
- **Protocol <Name>:** Provider-specific methods (e.g., `Protocol IBKR`)
- **Magic:** Magic methods (`__str__`, `__repr__`, etc.)

**Format:**
- Mark with `# region NAME` and `# endregion`
- Keep one empty line after `# region NAME` and before `# endregion`
- Remove all empty regions
- Order functions: more important first

## 8.2. Imports & Package Structure
- Import directly from source modules; **never re-export in `__init__.py`**
- After changes, remove unused imports and add missing ones
- Prefer namespace packages
- Only create `__init__.py` for executable code (e.g., `__version__`)

**Acceptance checks:**
- [ ] Regions follow naming/spacing rules; no empty regions
- [ ] No re-exports from `__init__.py`; imports are clean

## 8.3. Markdown Formatting
Keep all Markdown lines (including code blocks) **≤100 chars**. Break at natural points.

---

# 9. Testing Guidelines

- **Do not generate tests unless explicitly asked**
- Use **pytest** (not unittest)
- Test function names start with `test_` and describe what they test
- Organize: `tests/unit/` and `tests/integration/`
- Mirror package structure of code under test
- Keep only root `tests/__init__.py` file

---

# 10. Git Commit Guidelines

## 10.1. Critical Rule
**Never auto-commit:** Do not create commits, tags, or pushes unless explicitly requested by
user in current message.

## 10.2. Commit Format
- **Imperative mood** (command form): ✅ "Add user auth"; ❌ "Added user auth"
- **Subject line:** ≤50 chars, capital letter, no period at end
- Use present tense imperative verbs: Add, Fix, Remove, Update
- Be descriptive about what and why
- For longer commits: add body separated by blank line

---

# 11. Plan & Code Change Visualization

When proposing changes, show per-file Before/After snippets with minimal unique context.
Use fenced code blocks, keep lines ≤100 chars, include acceptance checks, update imports.

**Template:**

**Step X — Short description**

File: `path/to/file.py`
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
