---
apply: always
---

# Modern Algorithmic Trading Framework - Development Guidelines

**Project**: Python framework for backtesting and live trading.

---

# 1. Core Principles & Development Philosophy

## 1.1. Design Principles
- **KISS (Keep It Simple, Stupid):** Simplest working solution
- **YAGNI (You Aren't Gonna Need It):** Implement only when actively required
- **DRY (Don't Repeat Yourself):** No duplication of information, logic, or business rules
- **Intuitive Domain Model:** Keep objects simple; names/flows match trading mental model
- **Single Responsibility:** Each class has one distinct purpose
- **Separation of Concerns:** Divide responsibilities into distinct sections
- **Principle of Least Surprise:** Behavior aligns with user expectations
- **User-Centric API:** Design for users, not internal convenience

## 1.2. Development Mode
**Breaking changes allowed** during initial development. Backward compatibility is out of scope.
Remove or redesign anything to achieve optimal design.

### 1.2.1. Breaking Changes Policy (No Shims)
- We intentionally allow breaking API and module changes at any time
- Do not add deprecation shims, re‑exports, aliases, or compatibility layers.
- When relocating/renaming modules or classes, update all references in the codebase and documentation in the same
  change.
- Leave clear error messages in truly unavoidable stubs only when removal is technically impossible in the tooling;
  stubs must raise ImportError with a pointer to the new path.

---

# 2. Naming Conventions & API Design

## 2.1. General Naming Rules
Names must be **descriptive, intuitive, self-documenting and with natural English phrasing**.
Use Python `snake_case`. Avoid abbreviations. If possible, try to be concise, but never sacrifice clarity.

- **Functions/Methods:** Use verbs describing the action
- **Variables/Attributes:** Use nouns describing the data
- **Domain terms:** Use consistently;

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

## 3.2. Decimal utilities (DecimalLike, as_decimal)

When working with `decimal.Decimal` values (prices, quantities, P&L, ratios, fees), use `suite_trading.utils.decimal_tools`.

- Prefer `as_decimal(value)` over ad-hoc conversions like `Decimal(str(value))`.
- Use `DecimalLike` for public inputs that accept a "Decimal-ish" scalar (`Decimal | str | int | float`).
- Keep computed return types as `Decimal`.

Default import:

```python
from suite_trading.utils.decimal_tools import DecimalLike, as_decimal
```

Decimal-heavy modules (many conversions/Decimal operations) may use a local shortcut:

```python
from suite_trading.utils.decimal_tools import as_decimal as D  # D = as_decimal
```

Rules:
- Use `D` only in Decimal-heavy modules.

## 3.3. Parameter Layout in Calls

When calling functions/methods/constructors, keep simple argument lists on a single line for fast scanning.

### One-Line Parameters Rule
- If arguments are only simple values, keep the entire call on one line — even if >150 chars.
- "Simple" means: names/attributes (e.g., `qty`, `order.id`), literals (`10`, `"USD"`, `True`, `None`), and simple
  `key=value` pairs.
- Do not split such calls across multiple lines just for visual width.

### When to use multi-line
- Use multi-line layout only if any argument contains complex logic: nested calls, arithmetic/boolean chains,
  comprehensions, lambdas, ternary expressions, or long f-strings.
- In multi-line layout:
  - Put one argument per line.
  - Keep a trailing comma and align the closing parenthesis with the start of the call.

### Examples
```python
# ✅ Good — simple arguments kept on one line (fast to read)
order = Order(instrument, side, quantity, limit_price, tif, reduce_only=False, client_tag="alpha_v1")

# ❌ Bad — splitting simple arguments without need
order = Order(
    instrument,
    side,
    quantity,
    limit_price,
    tif,
    reduce_only=False,
    client_tag="alpha_v1",
)

# ✅ Good — multi-line because arguments contain expressions/nested calls
order = Order(
    instrument,
    compute_qty(signal, position, risk_model),
    side,
    compute_limit_price(book.best_bid(),
    slippage=bps_to_price(2, instrument)),
    client_tag=f"alpha_{now().date()}",
)

# ✅ Good — method call with only simple params stays on one line
broker.place_order(strategy_name, instrument, side, quantity, limit_price, tif)
```

**Acceptance checks:**
- [ ] Calls with only simple arguments are written on a single line (even if >150 chars)
- [ ] Multi-line layout is used only when any argument includes an expression or nested call
- [ ] Multi-line calls use one-argument-per-line with a trailing comma and aligned closing parenthesis

---

# 4. Documentation, Comments & Messaging

This section covers all developer-facing text: docstrings, comments, logs, and exceptions.

**Language policy:** All code, docstrings, comments, logs, and exceptions must be written in English.

## 4.1. Docstrings (Public API Documentation)

**Purpose:** Document public APIs for external developers.

**Requirements:**
- Google-style format: purpose, params, returns, exceptions, types
- **Simple, conversational English** - avoid complex or very technical jargon
- Include all important information; explain complex concepts simply
- Make immediately understandable without research
- Use concrete examples when helpful

**Example:**
```python
def calculate_portfolio_value(positions: list) -> Decimal:
    """Calculates the total value of all positions in a portfolio.

    This sums the market value of each position based on current prices.
    Positions with zero absolute_quantity are excluded from the calculation.

    Args:
        positions: List of Position objects with instrument and absolute_quantity.

    Returns:
        Total portfolio value as a Decimal.

    Raises:
        ValueError: If any position has invalid price data.
    """
    ...
```

## 4.2. Code Comments (Internal Documentation)

**Purpose:** Explain "why" and "what" of complex logic for maintainers. Reduces mental load and makes AI-assisted refactoring safer.

### Narrative Comments
- Short "why/what" comment above each logical unit
- Use domain terms and explicit states
- Explain business logic and reasoning
- Use simple conversational English

### Inline Line Comments for Code Scan-ability
- Add short, simple, and intuitive line comments to allow quick scanning of the logic without needing to parse complex code.
- Keep comments focused on what the next line or tiny block does, in 3–8 simple words.
- Use natural English phrases that match the trading mental model.
- Do not explain obvious assignments or one-liners that are already self-explanatory.

**Example:**

```python
# ACTIONS
# Set submission time into order
if self._timeline_dt is not None:
    order._set_submitted_dt_once(self._timeline_dt)

# Store order
self._orders_by_id[order.id] = order

# Do order-state transitions
for action in order_actions_to_apply:
    self._apply_order_action(order, action)

# Handle order expiration
if self._should_expire_order_now(order):
    self._apply_order_action(order, OrderAction.EXPIRE)
    return

# Match order with order-book
last_order_book = self._latest_order_book_by_instrument.get(order.instrument)
if last_order_book is not None:
    self._match_order_against_order_book(order, last_order_book)
```

**Acceptance checks:**
- [ ] Non-trivial lines/blocks have short, intuitive inline comments for fast scanning
- [ ] Comments allow scanning the logic without "executing" the code in your head
- [ ] Comments describe what the next line or tiny block does (not restate the code)
- [ ] Trivial, obvious assignments and one-liners have no extra comments

### Defensive Comments
- Use **`# Precondition:`** prefix for validation guards that raise an exception if the condition is not met.
- Use **`# Check:`** prefix for other validation guards where no exception is raised (e.g., early return, continue, or log and skip).
- Place **immediately above** validation check
- Explain what condition is validated and why it matters

#### Guard Block Spacing
- After a contiguous block of validation guards, insert exactly one empty line before the
  next block of code that performs actions (assignments, object creation, I/O, state changes).
  This visual separation improves scan-ability and emphasizes the boundary between validation
  and behavior.

### Code Reference Formatting
Apply to comments, docstrings, and error messages:
- **Parameters/attributes/variables:** `$parameter_name`
- **Functions/methods:** `` `function_name` ``

**Example:**

```python
# Collect fills since last event and net the absolute_quantity
fills = broker.get_fills_since(self._timeline_dt)
absolute_quantity = sum(f.absolute_quantity for f in fills)

# Check: ensure we have absolute_quantity to trade before submitting order
if absolute_quantity == 0:
  return

# Send order and record submission time
broker.submit(Order(instrument, side, absolute_quantity))
self._last_order_time = now()
```

**Acceptance checks:**
- [ ] `# Precondition:` or `# Check:` used only for validation guards
- [ ] Placed immediately above guard
- [ ] Code reference formatting followed (`$var`, `` `func` ``)
- [ ] One empty line after a guard block before state-changing code

### Section Header Comments

- Use ALL CAPS for comments that label a multi-line section.
- Keep a short noun phrase; parentheses optional.
- No trailing period; lines ≤150 chars.
- Use to group related API methods or logic inside a region or long function.
- Scope: from header until the next ALL‑CAPS header at the same indentation or the end of the region.
- Only use when at least two following lines belong to the section.

Examples:
```python
# Short example — group two small sections

# region Interface

# FUNDS
def list_funds_by_currency(self) -> list[tuple[Currency, Money]]: ...
def get_funds(self, currency: Currency) -> Money: ...

# MARGIN (PER-INSTRUMENT)
def block_initial_margin_for_instrument(self, instrument: Instrument, amount: Money) -> None: ...
def unblock_all_initial_margin_for_instrument(self, instrument: Instrument) -> None: ...

# endregion
```

```python
# More scenarios — inside a long function

def place_order(self, order: Order) -> None:
  # PARAM VALIDATION
  if order.absolute_quantity <= 0:
    raise ValueError(f"Cannot call `place_order` because $order.absolute_quantity ({order.absolute_quantity}) <= 0")

  # ACTIONS (SIDE EFFECTS)
  self._state = "SUBMITTED"
  self._last_order_dt = now()
  broker.submit(order)
```

```python
# More scenarios — inside a Properties region

# region Properties

# ORDER (IDENTITY)
@property
def order_id(self) -> str: ...

@property
def client_order_id(self) -> str: ...

# PRICES (SNAPSHOT)
@property
def last_price(self) -> Money: ...

@property
def bid_ask(self) -> tuple[Money, Money]: ...

# endregion
```

```python
# Anti-examples — do not do this

# Validation.  # Trailing period — wrong
if qty <= 0: ...

# Validation   # Not ALL CAPS — wrong
if qty <= 0: ...
```

Acceptance checks:
- [ ] Header comments used only for multi-line sections (≥2 following lines)
- [ ] Headers are ALL CAPS (parentheses optional) and have no trailing period
- [ ] Scope ends at the next ALL‑CAPS header at the same indentation or region end
- [ ] Lines ≤150 chars

### Validation Scope & Priorities

- Validate only important, common, or risky issues and domain relationships that are likely
  to go wrong.
- Focus guards on domain invariants and cross-object relationships (e.g., non-positive
  order quantity, time ranges with $start_dt > $end_dt, inconsistent $instrument between
  legs of a spread, unsupported venues for a given $instrument).
- Do not clutter code with trivial checks that Python and type checkers already cover:
  types, existence of attributes, or obvious None access that would fail fast on its own.
  Prefer clear type hints and let errors surface naturally.
- Keep validations cheap and close to boundaries. Avoid repeating the same guard in hot
  paths; validate once at the API boundary or where ownership is clear.
- Use the `# Precondition:` prefix only for meaningful guards as described above; do not use it
  for type/attribute presence checks.

**Acceptance checks:**
- [ ] Validation guards focus on important/risky domain invariants and relationships
- [ ] No guards added for trivial type/attribute existence checks or obvious None access

## 4.3. Logging

**Core rules:** Logs must be **precise, consistent, easy to scan**.

### Formatting Requirements
- ✅ **Always use f-strings** for interpolation
- ❌ **Never use** logger format args: `logger.info("msg %s", var)`
- ❌ **Never use** `.format()`: `"msg {}".format(var)`
- ❌ **Never use** `%` formatting: `"msg %s" % var`

### **CRITICAL: One-Line Rule**
**Every logger call must be a single line**, even if >150 chars. Do not wrap logger calls.

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
- If the entire `raise` call fits on one line, write it on a single line; do not wrap it across lines

**Short message — Preferred (one line):**

```python
if self.absolute_quantity <= 0:
  raise ValueError(f"Cannot call `_validate` because $absolute_quantity ({self.absolute_quantity}) is not positive")
```

**Short message — Wrong (wrapped unnecessarily):**

```python
if self.absolute_quantity <= 0:
  raise ValueError(
    f"Cannot call `_validate` because $absolute_quantity ({self.absolute_quantity}) is not positive"
  )
```

**Template (long message that doesn't fit on one line):**
```python
raise ValueError(
    f"Cannot call `start_strategy` because $state ('{self.state}') is not NEW. "
    f"Call `reset` or create a new Strategy."
)
```

**Example (long message):**
```python
raise ValueError(
    f"Cannot submit Order with $absolute_quantity ({quantity}) <= 0. "
    f"Provide a positive absolute_quantity or call `cancel_order` instead."
)
```

**Acceptance checks:**
- [ ] For short messages, the entire `raise` statement is a single line (not wrapped)
- [ ] Exception messages use f-strings with project terms and variable markers
- [ ] Message text itself is a single line even when the `raise` spans multiple lines

## 4.5. Readability & Debuggability

Keep expressions simple and easy to inspect in a debugger.

### Rules
- Avoid long, nested expressions in `return` statements or constructor calls. Extract
  sub-expressions into well‑named local variables.
- When constructing a non-trivial return value, assign it to a local variable named
  `result` and `return result`. Returning a simple name or literal directly is fine.
- Prefer short, single-purpose statements over clever one‑liners.

### Example
```python
# ❌ Bad — long nested return makes debugging hard
return Money(
    compute_notional_value(price, signed_quantity, instrument.contract_size) * self._maintenance_ratio,
    instrument.settlement_currency,
)

# ✅ Good — extract into locals and return `result`
notional = compute_notional_value(price, signed_quantity, instrument.contract_size)
margin = notional * self._maintenance_ratio
currency = instrument.settlement_currency
result = Money(margin, currency)
return result
```

**Acceptance checks:**
- [ ] No multi-line `return` with nested calls; complex expressions are broken into locals
- [ ] Non-trivial return values are assigned to `result` before returning
- [ ] Statements remain ≤150 chars per line where practical (see 8.3)

### Workflow decomposition (`Validate` → `Compute` → `Decide` → `Act`)

Apply this structure to any logic with non-trivial complexity (functions, pipelines, loops, or multi-step handlers).
It ensures the implementation is predictable and testable by separating pure derivations from side effects.

**Standard stages (top-to-bottom):**
- **`Validate`**: Cheap guards and domain invariants (e.g., check `$quantity > 0`). Return early or raise clear errors. No state changes.
- **`Compute`**: Pure, deterministic derivations (signals, prices, quantities). No I/O, no broker calls, no logging.
- **`Decide`**: Turn computed data into decisions by building "intent" objects (e.g., `Order` or `Adjustment`). Avoid side effects.
- **`Act`**: Perform side effects (submit/cancel orders, mutate state, emit logs, write files). Keep this stage small and explicit.

**Flexibility & Variants:**
- **Merge `Compute` & `Decide`**: In simpler scenarios, these can be merged into a single pure block that transforms input data directly into intent.
  The key principle remains separating pure logic from side effects.
- **Strict Boundary**: The most critical separation is between pure logic (`Compute`/`Decide`) and side effects (`Act`).
  This allows testing the core logic in isolation without mocks or complex setups.

**Acceptance checks:**
- [ ] Logic reads top-to-bottom as: `Validate` → [`Compute` → `Decide`] → `Act`
- [ ] Derivations (`Compute` and `Decide`) are pure: no hidden I/O, logging, or state mutations
- [ ] Side effects happen only in `Act` (easy to review and test)

### Workflow visualization (ASCII diagrams)

For complex workflows, add a compact tree diagram that shows the call sequence and stage boundaries.
This is mainly so we can compare the complexity of alternative approaches during refactors.

- **Compute:** pure functions only (no I/O, no logging, no broker/account mutations)
- **Act:** may have side effects (logging, broker calls, state mutation)

**Template (compact):**

```text
function_name(...)
├── [VALIDATE] validate_*()  -> cheap guards, early return / clear error
├── [COMPUTE]  compute_*()   -> pure derivations (no side effects)
├── [DECIDE]   decide_*()    -> build intent
└── [ACT]      act_*()       -> side effects
```

**Example (real workflow, keep it short):**

```text
_process_proposed_fill(order, proposed_fill, order_book)
├── [VALIDATE] Check instrument match
├── [COMPUTE]
│   ├── position_before, net_qty_after
│   ├── commission_margins = _compute_commission_margins_for_proposed_fill(...)
│   └── funds_now = get_funds(...)
├── [DECIDE] IF not has_enough_funds(...): handle insufficient funds
└── [ACT]
    ├── order_fill = _commit_proposed_fill_and_accounting(...)
    ├── publish order fill callback
    └── _handle_order_update(order)
```

**Acceptance checks:**
- [ ] Diagram is compact and helps compare alternative approaches during refactors
- [ ] Compute steps are pure (no hidden I/O, no logging, no broker/account mutations)
- [ ] Side effects are confined to Act (logging, broker calls, state mutation)

---

# 5. Class Design & Structure

## 5.1. Class Usage Guidelines
- **Standard Classes:** Use for fundamental domain models
- **Dataclasses/NamedTuples:** Only for simple config or value objects

## 5.2. String Representation (`__str__`, `__repr__`)

**Always include** `self.__class__.__name__` to make object types clear.

**Datetime formatting:** Use utilities from `suite_trading.utils.datetime_tools`:
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
- State the justification, invariant(s), or performance reason in the docstring if the reason for the abstraction is not obvious from the context.

**Example:**
```python
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
- [ ] New abstractions have a clear justification in their docstring if the reason for their existence is not obvious
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

## 7.2. Pricing terminology

- Do not use the term "mark price" anywhere in this codebase (code, docs, comments, logs,
  or tests). Use "last price" instead.

## 7.3. Broker and SimBroker semantics

**Core rules:**

- One `Broker` instance (like `SimBroker`) represents one logical trading account.
- Account-level data (cash, margin, positions, open orders) must never mix multiple accounts
  inside a single Broker instance.
- Multiple accounts are modelled by multiple Broker instances added to a `TradingEngine` via
  `add_broker(name, broker)`.

**SimBroker usage:**

- A `SimBroker` instance holds state for exactly one simulated account (orders, order fills,
  positions, account snapshot, last OrderBook per instrument).
- To simulate multiple accounts you must create multiple `SimBroker` instances (for example,
  `"sim_portfolio"`, `"sim_A"`, `"sim_B"`) and register them under different names.
- Strategies that share a `SimBroker` share one simulated account; strategies wired to
  different `SimBroker` instances are account-isolated.

**Responsibilities split:**

- Brokers simulate realistic order lifecycle, order fills, margin, and fee handling for their
  account.
- `TradingEngine` records order fills per Strategy and provides the raw data for backtest
  statistics.
- Reporting utilities should reconstruct per-Strategy and portfolio metrics from order fills and
  positions instead of embedding reporting into Broker implementations.

# 8. Code Organization

## 8.1. Regions
Use `# region NAME` / `# endregion` to group related blocks (no tiny regions).

Preferred baseline set and order:
1) Init, 2) Protocol <Name>, 3) Main, 4) Properties, 5) Utilities, 6) Magic.

These are **examples and a strong default**, not a hard whitelist.
It is allowed (and sometimes preferred) to introduce additional region names when it materially improves
scan-ability for a large class or module.

When adding a custom region name:
- The region must contain a meaningful multi-line block (no tiny regions).
- The region name must be descriptive and domain-relevant (e.g., `Order matching`, `Account & margin`, `Default builders`).
- Keep region names short and simple (ideally 1–2 words).
- Keep **public-first ordering**: public/protocol APIs must appear before helper-only regions.
- Keep the baseline regions where they fit (Init first; Magic last).

- Use `Protocol <Name>` for protocol API (see 8.5). Use `Main` only for public API not in a
  protocol. Standardize on `Utilities` (do not use "Helpers").
- For large classes, avoid a single giant `Utilities` region. Prefer decomposing helpers into multiple
  regions named `Utilities - <Topic>` where `<Topic>` is short (for example, `Utilities - Orders`, `Utilities - Positions`).
- Public‑first order (see 8.4). Remove empty regions.

**Format:**
- Mark with `# region NAME` and `# endregion`
- Keep one empty line after `# region NAME` and before `# endregion`
- Remove all empty regions
- Follow the ordering rules in 8.4

## 8.2. Imports & Package Structure
- Import directly from source modules; **never re-export in `__init__.py`**
- After changes, remove unused imports and add missing ones
- Prefer namespace packages
- Only create `__init__.py` for executable code (e.g., `__version__`)

**Acceptance checks:**
- [ ] Regions follow naming/spacing rules; no empty regions
- [ ] No re-exports from `__init__.py`; imports are clean

## 8.3. Markdown Formatting
Keep all Markdown lines (including code blocks) **≤150 chars**. Break at natural points.

## 8.4. Method ordering inside classes
- Order methods by reader importance:
  1) Init (constructor), 2) Public API ("Main"), 3) Properties,
     4) Protected/Private helpers ("Utilities"), 5) Magic (dunder).
- Use regions to mark these blocks: `# region Init`, `# region Main`, `# region Properties`,
  `# region Utilities` (or `# region Utilities - <Topic>`), `# region Magic`.
- Do not place protected/private helpers above public API unless there is a strong, documented
  reason.

Acceptance checks:
- [ ] Public API appears before protected/private helpers in each class
- [ ] Regions used and correctly named; no empty regions
- [ ] Reviews must call out violations explicitly

## 8.5. Region naming for protocol implementations
- When a class implements a Protocol's public API, name the region `Protocol <Name>` instead of
  the generic `Main`.
- Examples:
  - Use `# region Protocol MarginModel` in a margin model implementation.
  - Use `# region Protocol FeeModel` in a fee model implementation.

Acceptance checks:
- [ ] Classes implementing a Protocol use `Protocol <Name>` region for public API
- [ ] No leftover `Main` region when a protocol name would be clearer

## 8.6. Region naming and order (concise rule)
- Treat `Init`, `Protocol <Name>`, `Main`, `Properties`, `Utilities`, `Magic` as a preferred baseline
  and default ordering.
- Additional region names are allowed when justified and reasonable (see 8.1).
- Public‑first: `Init` → `Protocol <Name>`/`Main` → the rest. See 8.4 for details.
- If a class implements a Protocol, group those methods under `Protocol <Name>` (e.g., `Protocol
  MarginModel`). If multiple protocols, create one region per protocol.
- Use `Main` only for public API that is not part of any Protocol. Omit `Main` if the class is
  protocol‑only.
- Standardize on `Utilities` for non‑public helpers; do not use "Helpers".
- For large helper surfaces, you may split helpers across multiple regions using the `Utilities - <Topic>`
  naming convention.
- In modules that define a Protocol/interface, you may use a single `Interface` region.

Acceptance checks:
- [ ] `Protocol <Name>` is used instead of `Main` for protocol API (8.5)
- [ ] Public API appears before helpers (`Init` → `Protocol`/`Main`) (8.4)
- [ ] Region names are descriptive; the baseline order is respected; no "Helpers"
- [ ] No empty regions; remove unused headings (8.1)

---

# 9. Testing Guidelines

- **Do not automatically run tests**; the maintainer will run tests manually to save tokens/resources
- **Do not generate tests unless explicitly asked**
- Use **pytest** (not unittest)
- Test function names start with `test_` and describe what they test
- Organize: `tests/unit/` and `tests/integration/`
- Mirror package structure of code under test
- Keep only root `tests/__init__.py` file

## 9.1. Choosing test location and package

Place new tests based on what they exercise:

- Use `tests/unit/` when the test focuses on a single component or a very small group of
  closely related functions or classes. These tests should run fast, use simple fixtures,
  and avoid real I/O, databases, or external services.
- Use `tests/integration/` when the test covers multiple layers or components working
  together (for example, broker + engine + event-feed), or when it relies on realistic
  scenarios, external boundaries, or non-trivial I/O.

In both cases, choose the most specific and representative package under `tests/` so that
the test path mirrors the production module it covers. For example, tests for
`suite_trading.broker.simbroker` should live in `tests/unit/broker/` or
`tests/integration/broker/` with a file name like `test_simbroker.py`. Avoid dumping
unrelated tests into generic modules such as `tests/unit/test_misc.py`.

If in doubt, start in `tests/unit/`. Move or duplicate the scenario into
`tests/integration/` only when it clearly spans several layers or depends on realistic
wiring between components.

## 9.2. Use DataGenerationAssistant (`DGA`) for test data

Use the shared `DataGenerationAssistant` (`DGA`) from
`suite_trading.utils.data_generation.assistant` for creating common domain objects
in tests and examples.

The `DataGenerationAssistant` is a lightweight, stateless entry point that
exposes small factory namespaces. Each call creates fresh objects, so there is
no shared mutable state between tests.

Currently it provides:
- `instrument`: Helpers for creating `Instrument` fixtures (for example,
  realistic futures, FX, or equity instruments).
- `bar`: Helpers for creating single bars and bar series.
- `order_book`: Helpers for creating simple `OrderBook` snapshots from
  numeric tuples or "price@volume" strings.
- `trade_tick`: Helpers for creating trade ticks and series.
- `quote_tick`: Helpers for creating quote ticks and series.
- `pattern`: Helpers for scalar price patterns (linear, sine wave, zig-zag).

In new tests you should:
- Import `DGA` once, and
- Use its factories instead of manually constructing domain objects.

Preferred import pattern:

```python
from suite_trading.utils.data_generation.assistant import DGA


def test_example_instrument():
  instrument = DGA.instrument.future_es()
  # use $instrument in your test logic here
```

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
Use fenced code blocks, keep lines ≤150 chars, include acceptance checks, update imports.

For workflow/pipeline refactors, also include a `Validate` → `Compute` → `Decide` → `Act` ASCII diagram (see 4.5).

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
