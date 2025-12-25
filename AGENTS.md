# Modern Algorithmic Trading Framework - Development Guidelines

**Project**: Python framework for backtesting and live trading.

---

# 0. Rule Priorities & Conflict Resolution

When rules conflict, apply this priority order (highest first):

| Priority | Rule | Overrides |
|----------|------|-----------|
| P1 | **One-Line Rule** (R-4.3.1): Logger calls and exception messages on single line | Line length limits |
| P2 | **Simple Args One-Line** (R-3.3.1): Function calls with simple args on single line | Line length limits |
| P3 | **≤150 chars** (R-5.3.1): General line length limit | — |

**Example of P1 overriding P3:**
```python
# ✅ Correct — One-Line Rule (P1) wins over ≤150 chars (P3)
logger.debug(f"EventFeed named '{feed_name}' for Strategy named '{strategy_name}' in TradingEngine '{engine_name}' was already finished with status '{status}'")

# ❌ Wrong — Breaking line to satisfy ≤150 chars violates One-Line Rule
logger.debug(
    f"EventFeed named '{feed_name}' for Strategy named '{strategy_name}' "
    f"in TradingEngine '{engine_name}' was already finished"
)
```

---

# 1. Core Principles & Development Philosophy

## 1.1. Design Principles
- **R-1.1.1 KISS (Keep It Simple, Stupid):** Simplest working solution
- **R-1.1.2 YAGNI (You Aren't Gonna Need It):** Implement only when actively required
- **R-1.1.3 DRY (Don't Repeat Yourself):** No duplication of information, logic, or business rules
- **R-1.1.4 Intuitive Domain Model:** Keep objects simple; names/flows match trading mental model
- **R-1.1.5 Single Responsibility:** Each class has one distinct purpose
- **R-1.1.6 Separation of Concerns:** Divide responsibilities into distinct sections
- **R-1.1.7 Principle of Least Surprise:** Behavior aligns with user expectations
- **R-1.1.8 User-Centric API:** Design for users, not internal convenience

## 1.2. Development Mode
**R-1.2.1** Breaking changes allowed during initial development. Backward compatibility is out of scope.
Remove or redesign anything to achieve optimal design.

### Breaking Changes Policy (No Shims)
- **R-1.2.2** We intentionally allow breaking API and module changes at any time
- **R-1.2.3** Do not add deprecation shims, re‑exports, aliases, or compatibility layers
- **R-1.2.4** When relocating/renaming modules or classes, update all references in the codebase and documentation in the same change
- **R-1.2.5** Leave clear error messages in truly unavoidable stubs only when removal is technically impossible; stubs must raise ImportError with a pointer to the new path

---

# 2. Naming Conventions & API Design

## 2.1. General Naming Rules
**R-2.1.1** Names must be **descriptive, intuitive, self-documenting and with natural English phrasing**.
Use Python `snake_case`. Avoid abbreviations. If possible, try to be concise, but never sacrifice clarity.

**Exception:** The shortcut `abs_` is allowed instead of the full word `absolute_` (e.g., `abs_quantity`, `abs_position_quantity_change`).

- **R-2.1.2** Functions/Methods: Use verbs describing the action
- **R-2.1.3** Variables/Attributes: Use nouns describing the data
- **R-2.1.4** Domain terms: Use consistently throughout codebase

```python
# ✅ Good — descriptive, natural English
def calculate_unrealized_pnl(position: Position, current_price: Decimal) -> Decimal: ...
def list_open_orders(instrument: Instrument) -> list[Order]: ...

# ❌ Bad — abbreviated, unclear
def calc_pnl(pos, px): ...
def get_ords(inst): ...
```

## 2.2. Method Naming Patterns

| Pattern | Purpose | Examples |
|---------|---------|----------|
| `list_*` | Return collections | `list_active_orders()`, `list_open_positions()` |
| `get_*` | Retrieve existing single resource (cheap, no modeling) | `get_account_info()`, `get_order(order_id)`, `get_best_bid()` |
| `build_*` / `create_*` | Construct/model new objects (signals expensive operation) | `build_order_book(sample)`, `create_snapshot(now)` |
| `compute_*` | Derived numeric metrics requiring calculation | `compute_realized_pnl(trades)`, `compute_sharpe(returns)` |
| `find_*` / `query_*` | Search/filter with partial/empty results | (optional, future scope) |

```python
# ✅ Good — correct pattern usage
orders = broker.list_open_orders()           # Returns collection
order = broker.get_order(order_id)           # Retrieves single, cheap
book = builder.build_order_book(ticks)       # Expensive construction
pnl = analytics.compute_sharpe(returns)      # Calculation

# ❌ Bad — wrong pattern
orders = broker.get_open_orders()            # Should be list_* for collection
order = broker.find_order(order_id)          # Should be get_* for direct retrieval
book = builder.get_order_book(ticks)         # Should be build_* for construction
```

## 2.3. Parameter Design & Ordering
- **R-2.3.1** Order by Importance: Always place the most important parameters first. The first parameter should be the primary subject of the function—the object it primarily acts upon, calculates for, or transforms.
- **R-2.3.2** Subject vs. Context: Distinguish between the primary subject and secondary context (e.g., historical data, reference models, or configuration). Secondary context parameters should follow the primary subject.
- **R-2.3.3** Mental Model Alignment: The parameter order should reflect the natural phrasing of the operation (e.g., "calculate commission for $proposed_fill using $order and $history").

```python
# ✅ Good — primary subject first, then context
def calculate_commission(proposed_fill: ProposedFill, order: Order, fee_model: FeeModel) -> Money: ...
#                        ↑ primary subject        ↑ context      ↑ configuration

# ❌ Bad — configuration before subject
def calculate_commission(fee_model: FeeModel, order: Order, proposed_fill: ProposedFill) -> Money: ...
```

---

# 3. Type Annotations & Signatures

## 3.1. Modern Typing Rules
**R-3.1.1** Always start modules with: `from __future__ import annotations`

**Required practices:**
- **R-3.1.2** Use direct type names (no quotes, no `"a.b.Type"` strings)
- **R-3.1.3** Builtin generics only: `list[T]`, `dict[K, V]`, `set[T]`, `tuple[...]`
- **R-3.1.4** Use `|` and `| None` instead of `Union`/`Optional`
- **R-3.1.5** Use `type[T]` for class objects
- **R-3.1.6** `Callable[[...], R]` with explicit return type
- **R-3.1.7** Import cross-module types unconditionally. Use `if TYPE_CHECKING:` only when strictly required to avoid circular runtime dependencies.

```python
# ✅ Good — modern typing
from __future__ import annotations

def process(items: list[Order], callback: Callable[[Order], None]) -> dict[str, int] | None: ...

# ❌ Bad — legacy typing
from typing import List, Dict, Optional, Union

def process(items: List[Order], callback: Callable) -> Optional[Dict[str, int]]: ...
```

## 3.2. Decimal Utilities (`DecimalLike`, `as_decimal`)

**R-3.2.1** When working with `decimal.Decimal` values (prices, quantities, P&L, ratios, fees), use `suite_trading.utils.decimal_tools`.

- **R-3.2.2** Prefer `as_decimal(value)` over ad-hoc conversions like `Decimal(str(value))`
- **R-3.2.3** Use `DecimalLike` for public inputs that accept a "Decimal-ish" scalar (`Decimal | str | int | float`)
- **R-3.2.4** Keep computed return types as `Decimal`

**Default import:**
```python
from suite_trading.utils.decimal_tools import DecimalLike, as_decimal
```

**R-3.2.5** Decimal-heavy modules (many conversions/Decimal operations) may use a local shortcut:
```python
from suite_trading.utils.decimal_tools import as_decimal as D  # D = as_decimal
```

## 3.3. Parameter Layout in Calls

**R-3.3.1** When calling functions/methods/constructors, keep simple argument lists on a single line for fast scanning.

### One-Line Parameters Rule
- **R-3.3.2** If arguments are only simple values, keep the entire call on one line — even if >150 chars
- **R-3.3.3** "Simple" means: names/attributes (e.g., `qty`, `order.id`), literals (`10`, `"USD"`, `True`, `None`), and simple `key=value` pairs
- **R-3.3.4** Do not split such calls across multiple lines just for visual width

### When to Use Multi-Line
- **R-3.3.5** Use multi-line layout only if any argument contains complex logic: nested calls, arithmetic/boolean chains, comprehensions, lambdas, ternary expressions, or long f-strings
- **R-3.3.6** In multi-line layout: put one argument per line, keep a trailing comma and align the closing parenthesis with the start of the call

### Examples
```python
# ✅ Good — simple arguments kept on one line (fast to read), even if >150 chars
order = Order(instrument, side, quantity, limit_price, tif, reduce_only=False, client_tag="alpha_v1", broker_id="ib_main")

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
    compute_limit_price(book.best_bid(), slippage=bps_to_price(2, instrument)),
    client_tag=f"alpha_{now().date()}",
)
```

**Acceptance checks:**
- [ ] R-3.3.2: Calls with only simple arguments are written on a single line (even if >150 chars)
- [ ] R-3.3.5: Multi-line layout is used only when any argument includes an expression or nested call
- [ ] R-3.3.6: Multi-line calls use one-argument-per-line with a trailing comma and aligned closing parenthesis

---

# 4. Documentation, Comments & Messaging

**R-4.0.1** Language policy: All code, docstrings, comments, logs, and exceptions must be written in English.

## 4.1. Docstrings (Public API Documentation)

**Purpose:** Document public APIs for external developers.

**R-4.1.1** Format: Google-style (purpose, params, returns, exceptions, types)

**Requirements:**
- **R-4.1.2** Natural, Simple Phrasing: Use conversational English. Avoid technical jargon or overly formal wording
- **R-4.1.3** Identify the Primary Subject: Clearly state what the function is doing or calculating for
- **R-4.1.4** Explain Parameter Context: Describe the role of each parameter. Make it clear which is the main subject and which provide secondary context
- **R-4.1.5** Make immediately understandable without needing to research internal logic
- **R-4.1.6** Use concrete examples when helpful

```python
# ✅ Good — natural, identifies subject, explains context
def calculate_portfolio_value(positions: list) -> Decimal:
    """Calculates the total value of all positions in a portfolio.

    This sums the market value of each position based on current prices.
    Positions with zero abs_quantity are excluded from the calculation.

    Args:
        positions: List of Position objects with instrument and abs_quantity.

    Returns:
        Total portfolio value as a Decimal.

    Raises:
        ValueError: If any position has invalid price data.
    """
    ...

# ❌ Bad — technical jargon, unclear subject
def calculate_portfolio_value(positions: list) -> Decimal:
    """Aggregates NAV via position iteration.

    Iterates the position vector and accumulates notional values.

    Args:
        positions: Position vector.

    Returns:
        Decimal.
    """
    ...
```

**Acceptance checks:**
- [ ] R-4.1.2: Docstrings use natural, conversational English
- [ ] R-4.1.3: The primary subject of the function is clearly identified
- [ ] R-4.1.4: The role and context of each parameter are explained

## 4.2. Code Comments (Internal Documentation)

**Purpose:** Explain "why" and "what" of complex logic for maintainers. Reduces mental load and makes AI-assisted refactoring safer.

### Comment Types

#### Narrative Comments
- **R-4.2.1** Short "why/what" comment above each logical unit
- **R-4.2.2** Use domain terms and explicit states
- **R-4.2.3** Explain business logic and reasoning
- **R-4.2.4** Use simple conversational English

#### Inline Line Comments (for Code Scan-ability)
- **R-4.2.5** Add short, simple, and intuitive line comments to allow quick scanning of the logic
- **R-4.2.6** Keep comments focused on what the next line or tiny block does, in 3–8 simple words
- **R-4.2.7** Use natural English phrases that match the trading mental model
- **R-4.2.8** Do not explain obvious assignments or one-liners that are already self-explanatory

#### Section Header Comments
- **R-4.2.9** Use ALL CAPS for comments that label a multi-line section
- **R-4.2.10** Keep a short noun phrase; parentheses optional
- **R-4.2.11** No trailing period; lines ≤150 chars
- **R-4.2.12** Scope: from header until the next ALL‑CAPS header at the same indentation or the end of the region
- **R-4.2.13** Only use when at least two following lines belong to the section

```python
# ✅ Good — ALL CAPS, no period, groups related code
# MARGIN CALCULATION
initial = compute_initial_margin(order, price)
maintenance = compute_maintenance_margin(position, price)

# ❌ Bad — not ALL CAPS, has period
# Margin calculation.
initial = compute_initial_margin(order, price)
```

### Validation Guards

**Terminology:** Use "Precondition" for guards that raise exceptions, "Guard" for guards that return early or skip.

- **R-4.2.14** Use **`# Precondition:`** prefix for validation guards that raise an exception if the condition is not met
- **R-4.2.15** Use **`# Guard:`** prefix for validation guards where no exception is raised (e.g., early return, continue, or log and skip)
- **R-4.2.16** Place **immediately above** validation code
- **R-4.2.17** Explain what condition is validated and why it matters

```python
# ✅ Good — correct prefix usage
# Precondition: $abs_quantity must be positive to submit order
if order.abs_quantity <= 0:
    raise ValueError(f"Cannot call `submit_order` because $abs_quantity ({order.abs_quantity}) <= 0")

# Guard: skip processing if no fills available
if not fills:
    return

# ❌ Bad — wrong prefix (raises but uses Guard)
# Guard: quantity must be positive
if order.abs_quantity <= 0:
    raise ValueError("Invalid quantity")

# ❌ Bad — wrong prefix (returns but uses Precondition)
# Precondition: must have fills
if not fills:
    return
```

### Code Reference Formatting
**R-4.2.18** Apply to comments, docstrings, and error messages:
- **Parameters/attributes/variables:** `$parameter_name`
- **Functions/methods:** `` `function_name` ``

### Guard Block Spacing
**R-4.2.19** After a contiguous block of validation guards, insert exactly one empty line before the next block of code that performs actions (assignments, object creation, I/O, state changes)

```python
# ✅ Good — empty line after guard block
# Precondition: order must have valid instrument
if order.instrument is None:
    raise ValueError("...")

# Precondition: quantity must be positive
if order.abs_quantity <= 0:
    raise ValueError("...")

# Now perform actions (empty line above separates guards from actions)
self._orders[order.id] = order
broker.submit(order)

# ❌ Bad — no separation between guards and actions
# Precondition: order must have valid instrument
if order.instrument is None:
    raise ValueError("...")
# Precondition: quantity must be positive
if order.abs_quantity <= 0:
    raise ValueError("...")
self._orders[order.id] = order  # Action immediately after guard
```

### Examples

**Inline comments and sections:**
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

**Section headers inside regions:**
```python
# region Interface

# FUNDS
def list_funds_by_currency(self) -> list[tuple[Currency, Money]]: ...
def get_funds(self, currency: Currency) -> Money: ...

# MARGIN (PER-INSTRUMENT)
def block_initial_margin_for_instrument(self, instrument: Instrument, amount: Money) -> None: ...
def unblock_all_initial_margin_for_instrument(self, instrument: Instrument) -> None: ...

# endregion
```

**Validation guards with spacing:**
```python
# Collect fills since last event and net the abs_quantity
fills = broker.get_fills_since(self._timeline_dt)
abs_quantity = sum(f.abs_quantity for f in fills)

# Guard: skip if no quantity to trade
if abs_quantity == 0:
    return

# Send order and record submission time
broker.submit(Order(instrument, side, abs_quantity))
self._last_order_time = now()
```

**Acceptance checks:**
- [ ] R-4.2.5: Non-trivial lines/blocks have short, intuitive inline comments
- [ ] R-4.2.9: Section headers are ALL CAPS with no trailing period
- [ ] R-4.2.14/R-4.2.15: `# Precondition:` for raises, `# Guard:` for early returns
- [ ] R-4.2.19: One empty line after guard block before state-changing code
- [ ] R-4.2.18: Code reference formatting followed (`$var`, `` `func` ``)

### Validation Scope & Priorities

- **R-4.2.20** Validate only important, common, or risky issues and domain relationships that are likely to go wrong
- **R-4.2.21** Focus guards on domain invariants and cross-object relationships (e.g., non-positive order quantity, time ranges with $start_dt > $end_dt, inconsistent $instrument between legs)
- **R-4.2.22** Do not clutter code with trivial validations that Python and type checkers already cover: types, existence of attributes, or obvious None access that would fail fast on its own
- **R-4.2.23** Keep validations cheap and close to boundaries. Avoid repeating the same guard in hot paths; validate once at the API boundary

```python
# ✅ Good — validates domain invariant (quantity sign)
# Precondition: $abs_quantity must be positive
if order.abs_quantity <= 0:
    raise ValueError(f"...")

# ❌ Bad — trivial type check (Python/mypy handles this)
# Precondition: order must be Order type
if not isinstance(order, Order):
    raise TypeError(f"...")

# ❌ Bad — obvious None that would fail naturally
# Precondition: instrument must exist
if order.instrument is None:
    raise ValueError(f"...")
# order.instrument.symbol  # Would fail with clear AttributeError anyway
```

**Acceptance checks:**
- [ ] R-4.2.20: Validation guards focus on important/risky domain invariants
- [ ] R-4.2.22: No guards for trivial type/attribute existence validations

## 4.3. Logging & Exception Messages

### Core Formatting Rules (apply to both)
- **R-4.3.1 (P1 PRIORITY)** One-Line Rule: Every logger call and exception message must be a single line, even if >150 chars. Do not wrap. This rule overrides the ≤150 char limit.
- **R-4.3.2** Always use f-strings for interpolation
- **R-4.3.3** Never use logger format args: `logger.info("msg %s", var)`
- **R-4.3.4** Never use `.format()`: `"msg {}".format(var)`
- **R-4.3.5** Never use `%` formatting: `"msg %s" % var`

### Logging Specifics

**Domain Object Identification:**
- **R-4.3.6** Strategies/EventFeeds: `"Strategy named '{strategy_name}'"`, `"EventFeed named '{feed_name}'"`
- **R-4.3.7** Concept/type only: use capitalized class name (`Strategy`, `EventFeed`, `Broker`)
- **R-4.3.8** Include instance class: `"(class {obj.__class__.__name__})"`

**Message Structure:**
- **R-4.3.9** Pattern: `"<Verb> <ClassName> named '{name}' <short context>"`
- **R-4.3.10** State transitions: `"ClassName named '{name}' transitioned to <STATE>"`
- **R-4.3.11** Errors: action/context → object → error

**Capitalization & Terminology:**
- **R-4.3.12** Capitalize domain class names when used as nouns
- **R-4.3.13** Use "event-feed" (hyphenated) for generic prose
- **R-4.3.14** Use `EventFeed` when referring to the class
- **R-4.3.15** Pluralization: "EventFeed(s)", "Strategy(ies)", "broker(s)"

```python
# ✅ Good — single line, f-string, correct pattern
logger.info(f"Started Strategy named '{strategy_name}'")
logger.debug(f"EventFeed named '{feed_name}' was already finished")
logger.error(f"Error closing EventFeed named '{feed_name}': {e}")

# ✅ Good — long line stays on single line (R-4.3.1 overrides line length)
logger.debug(f"EventFeed named '{feed_name}' for Strategy named '{strategy_name}' in TradingEngine '{engine_name}' finished with status '{status}'")

# ❌ Bad — wrapped across lines (violates R-4.3.1)
logger.debug(
    f"EventFeed named '{feed_name}' was already finished",
)

# ❌ Bad — using format args (violates R-4.3.3)
logger.info("Started Strategy '%s'", strategy_name)
```

### Exception Message Specifics

- **R-4.3.16** 100% clear, use project terms, guide the fix
- **R-4.3.17** Include function name in backticks: `` `function_name` ``
- **R-4.3.18** Identify variables with `$` and real names; include values when helpful
- **R-4.3.19** If the entire `raise` call fits on one line, write it on a single line; do not wrap

```python
# ✅ Good — short message on single line
if self.abs_quantity <= 0:
    raise ValueError(f"Cannot call `_validate` because $abs_quantity ({self.abs_quantity}) is not positive")

# ✅ Good — long message that truly doesn't fit uses continuation
raise ValueError(
    f"Cannot call `start_strategy` because $state ('{self.state}') is not NEW. "
    f"Call `reset` or create a new Strategy."
)

# ❌ Bad — short message unnecessarily wrapped
if self.abs_quantity <= 0:
    raise ValueError(
        f"Cannot call `_validate` because $abs_quantity ({self.abs_quantity}) is not positive"
    )
```

**Acceptance checks:**
- [ ] R-4.3.1: No wrapped logger calls or short raise statements; each is one line
- [ ] R-4.3.2: All logger/exception strings use f-strings
- [ ] R-4.3.9: Messages use naming/structure rules

## 4.4. Readability & Debuggability

Keep expressions simple and easy to inspect in a debugger.

### Rules
- **R-4.4.1** Avoid long, nested expressions in `return` statements or constructor calls. Extract sub-expressions into well‑named local variables
- **R-4.4.2** When constructing a non-trivial return value, assign it to a local variable named `result` and `return result`. Returning a simple name or literal directly is fine
- **R-4.4.3** Prefer short, single-purpose statements over clever one‑liners
- **R-4.4.4** Avoid creating one-time used variables for simple attribute access or trivial expressions (e.g., `currency = upfront_required.currency`). Inline them to keep the code concise unless the variable name provides significant documentation value or is required for breaking down a truly complex expression.

```python
# ❌ Bad — long nested return makes debugging hard
return Money(
    compute_notional_value(price, signed_quantity, instrument.contract_size) * self._maintenance_ratio,
    instrument.settlement_currency,
)

# ✅ Good — extract into locals and return `result`
notional = compute_notional_value(price, signed_quantity, instrument.contract_size)
margin = notional * self._maintenance_ratio
result = Money(margin, instrument.settlement_currency)
return result

# ✅ Good — simple return is fine without `result`
return self._balance

# ✅ Good — literal return is fine
return None
```

**Acceptance checks:**
- [ ] R-4.4.1: No multi-line `return` with nested calls; complex expressions are broken into locals
- [ ] R-4.4.2: Non-trivial return values are assigned to `result` before returning

## 4.5. Workflow Decomposition (`Validate` → `Compute` → `Decide` → `Act`)

**R-4.5.1** Apply this structure to any logic with non-trivial complexity (functions, pipelines, loops, or multi-step handlers).
It ensures the implementation is predictable and testable by separating pure derivations from side effects.

**Standard stages (top-to-bottom):**
- **R-4.5.2 `Validate`**: Cheap guards and domain invariants (e.g., check `$quantity > 0`). Return early or raise clear errors. No state changes
- **R-4.5.3 `Compute`**: Pure, deterministic derivations (signals, prices, quantities). No I/O, no broker calls, no logging
- **R-4.5.4 `Decide`**: Turn computed data into decisions by building "intent" objects (e.g., `Order` or `Adjustment`). Avoid side effects
- **R-4.5.5 `Act`**: Perform side effects (submit/cancel orders, mutate state, emit logs, write files). Keep this stage small and explicit

**Flexibility & Variants:**
- **R-4.5.6** Merge `Compute` & `Decide`: In simpler scenarios, these can be merged into a single pure block. The key principle remains separating pure logic from side effects
- **R-4.5.7** Strict Boundary: The most critical separation is between pure logic (`Compute`/`Decide`) and side effects (`Act`). This allows testing the core logic in isolation

### Workflow Visualization (ASCII Diagrams)

**R-4.5.8** For complex workflows, use a compact tree diagram during the design and proposal phase to show the call sequence and stage boundaries. **Do not include these diagrams in docstrings or comments in the final code.**

**Template (compact):**
```text
function_name(...)
├── [VALIDATE] validate_*()  -> cheap guards, early return / clear error
├── [COMPUTE]  compute_*()   -> pure derivations (no side effects)
├── [DECIDE]   decide_*()    -> build intent
└── [ACT]      act_*()       -> side effects
```

**Example:**
```text
_process_proposed_fill(order, proposed_fill, order_book)
├── [VALIDATE] Check instrument match
├── [COMPUTE]
│   ├── signed_position_quantity_before, maintenance_margin_before
│   ├── commission, initial_margin, maintenance_margin_change = _compute_commission_and_margin_changes(...)
│   └── funds_now = get_funds(...)
├── [DECIDE] IF not has_enough_funds(...): handle insufficient funds
└── [ACT]
    ├── order_fill = _commit_proposed_fill_and_accounting(...)
    ├── publish order fill callback
    └── _handle_order_update(order)
```

**Acceptance checks:**
- [ ] R-4.5.1: Logic reads top-to-bottom as: `Validate` → [`Compute` → `Decide`] → `Act`
- [ ] R-4.5.3/R-4.5.4: Derivations are pure: no hidden I/O, logging, or state mutations
- [ ] R-4.5.5: Side effects happen only in `Act`

---

# 5. Code Organization

## 5.1. Regions

**R-5.1.1** Use `# region NAME` / `# endregion` to group related blocks. Regions must contain meaningful multi-line blocks (no tiny regions).

### Baseline Region Set and Order
1. **Init** — constructor
2. **Protocol \<n\>** — protocol API implementation (e.g., `Protocol MarginModel`)
3. **Main** — public API not in a protocol
4. **Properties** — property methods
5. **Utilities** — non-public helpers (standardize on "Utilities", not "Helpers")
6. **Magic** — dunder methods

**R-5.1.2** These are examples and a strong default, not a hard whitelist. Additional region names are allowed when they materially improve scan-ability.

### Region Rules

**Naming:**
- **R-5.1.3** Region names must be descriptive and domain-relevant (e.g., `Order matching`, `Account & margin`)
- **R-5.1.4** Keep region names short and simple (ideally 1–2 words)
- **R-5.1.5** Use `Protocol <n>` for protocol API. Use `Main` only for public API not in a protocol
- **R-5.1.6** Standardize on `Utilities` (do not use "Helpers")
- **R-5.1.7** For large classes, prefer decomposing into `Utilities - <Topic>` (e.g., `Utilities - Orders`)
- **R-5.1.8** In modules that define a Protocol/interface, you may use a single `Interface` region

**Ordering:**
- **R-5.1.9** Public-first ordering: public/protocol APIs must appear before helper-only regions
- **R-5.1.10** Order: `Init` → `Protocol <n>`/`Main` → `Properties` → `Utilities` → `Magic`
- **R-5.1.11** Do not place protected/private helpers above public API unless there is a strong, documented reason
- **R-5.1.12** If a class implements a Protocol, group those methods under `Protocol <n>`. If multiple protocols, create one region per protocol
- **R-5.1.13** Omit `Main` if the class is protocol‑only

**Format:**
- **R-5.1.14** Mark with `# region NAME` and `# endregion`
- **R-5.1.15** Keep one empty line after `# region NAME` and before `# endregion`
- **R-5.1.16** Remove all empty regions

```python
# ✅ Good — correct naming, ordering, spacing
# region Init

def __init__(self, ...):
    ...

# endregion

# region Protocol MarginModel

def calculate_initial_margin(self, ...) -> Money:
    ...

# endregion

# region Properties

@property
def margin_ratio(self) -> Decimal:
    ...

# endregion

# region Utilities - Orders

def _validate_order(self, order: Order) -> None:
    ...

# endregion

# region Magic

def __str__(self) -> str:
    ...

# endregion

# ❌ Bad — wrong naming, wrong order
# region Helpers  # Should be "Utilities"

def _validate_order(self, order: Order) -> None:
    ...

# endregion

# region Main  # Public API after helpers — violates R-5.1.9

def submit_order(self, order: Order) -> None:
    ...

# endregion
```

**Acceptance checks:**
- [ ] R-5.1.6: No "Helpers" — use "Utilities"
- [ ] R-5.1.9: Public API appears before protected/private helpers
- [ ] R-5.1.5: `Protocol <n>` is used instead of `Main` for protocol API
- [ ] R-5.1.16: No empty regions

## 5.2. Imports & Package Structure
- **R-5.2.1** Import directly from source modules; **never re-export in `__init__.py`**
- **R-5.2.2** After changes, remove unused imports and add missing ones
- **R-5.2.3** Prefer namespace packages
- **R-5.2.4** Only create `__init__.py` for executable code (e.g., `__version__`)

**Acceptance checks:**
- [ ] R-5.2.1: No re-exports from `__init__.py`; imports are clean

## 5.3. Markdown Formatting
**R-5.3.1** Keep all Markdown lines (including code blocks) **≤150 chars**. Break at natural points.

**Note:** This rule has lower priority (P3) than One-Line Rule (P1) and Simple Args One-Line (P2). See Section 0.

---

# 6. Class Design & Structure

## 6.1. Class Usage Guidelines
- **R-6.1.1** Standard Classes: Use for fundamental domain models
- **R-6.1.2** Dataclasses/NamedTuples: Only for simple config or value objects

## 6.2. String Representation (`__str__`, `__repr__`)

**R-6.2.1** Always include `self.__class__.__name__` to make object types clear.

**R-6.2.2** Datetime formatting: Use utilities from `suite_trading.utils.datetime_tools`:
- `format_dt(dt)` for single timestamp
- `format_range(start_dt, end_dt)` for intervals

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
- [ ] R-6.2.1: `__str__`/`__repr__` use `self.__class__.__name__`
- [ ] R-6.2.2: Datetime utils used for timestamp formatting

## 6.3. Memory Optimization (`__slots__`)

**R-6.3.1** Use for classes with high instance counts (Bars, Ticks, Events) to reduce memory and improve speed.

**When to use:**
- High instance counts at runtime
- Fixed attribute schema
- No reliance on instance `__dict__`

### Critical Inheritance Rule
**R-6.3.2** If parent defines `__slots__`, every subclass MUST define `__slots__` too:
- Use `__slots__ = ()` when subclass adds no new fields
- Otherwise list private attribute names used in `__init__` (e.g., `"_price"`)
- Do not add `"__weakref__"` unless needed
- Include `"__dict__"` only when dynamic attrs required

```python
# ✅ Good — proper slots inheritance
class Event:
    __slots__ = ("_dt_event", "_dt_received")

class BarEvent(Event):
    __slots__ = ()  # No new instance fields

class QuoteTick(Event):
    __slots__ = ("_instrument", "_bid_price", "_ask_price", "_timestamp")

# ❌ Bad — subclass missing __slots__
class Event:
    __slots__ = ("_dt_event", "_dt_received")

class BarEvent(Event):
    pass  # Missing __slots__ = () — breaks memory optimization
```

**Acceptance checks:**
- [ ] R-6.3.1: `__slots__` defined for high-volume classes
- [ ] R-6.3.2: Subclasses of slotted classes define `__slots__` (use `()` when none)

## 6.4. Comparison & Sorting (`@total_ordering`)

**R-6.4.1** For any custom comparable type: Implement full ordering with `@total_ordering`.

**Requirements:**
- **R-6.4.2** Implement `__lt__` and ensure `__eq__` is defined
- **R-6.4.3** Return `NotImplemented` for different types
- **R-6.4.4** Single source of truth for ordering (precedence map/key function)
- **R-6.4.5** Annotate returns as `bool | NotImplementedType`

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
- [ ] R-6.4.1: Class decorated with `@total_ordering`
- [ ] R-6.4.3: `__lt__` returns `NotImplemented` for different types
- [ ] R-6.4.4: Single precedence map defined once
- [ ] R-6.4.5: Return type hints include `NotImplementedType`

---

# 7. Complexity Control & Premature Abstraction

**R-7.0.1** Core rule: Do not introduce new types, layers, helpers, or indirection unless gain is immediate, material, well-justified, and documented.

## 7.1. What This Means Now
- **R-7.1.1** Don't alias simple primitives: `Price = Decimal`, `Volume = Decimal`
- **R-7.1.2** Use explicit types: `tuple[Decimal, Decimal]`
- **R-7.1.3** Don't add wrapper classes for tuples/lists/dicts just to name fields

```python
# ✅ Good — explicit type
bids: Sequence[tuple[Decimal, Decimal]]

# ❌ Bad — unnecessary alias
Price = Decimal
Volume = Decimal
bids: Sequence[tuple[Price, Volume]]
```

## 7.2. When to Add New Value Object

**R-7.2.1** At least ONE must be true:
- Must enforce invariants/units/validation (currency, tick size, rounding)
- Attach behavior with data (methods, arithmetic with rounding rules)
- Measurable performance/memory improvements in hot paths
- Reused across **3+ call sites/modules** with real maintenance cost
- Represents external boundary (serialization schema, protocol, storage)

## 7.3. If Adding One
- **R-7.3.1** Prefer `NamedTuple` for read-only shapes
- **R-7.3.2** Or `@dataclass(frozen=True)` with `__slots__` when validation needed
- **R-7.3.3** State the justification, invariant(s) or performance reason in the docstring if not obvious

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
- [ ] R-7.1.1: No primitive aliases exposed in public APIs
- [ ] R-7.3.3: New abstractions have a clear justification in their docstring if not obvious
- [ ] R-7.2.1: Utils/wrappers only with 3+ reuse sites or explicit hot-path perf need

---

# 8. Domain-Specific Rules

## 8.1. Price Validation
**R-8.1.1** Negative prices are allowed when market supports them. Do not reject negative `$price` values in generic validation.

**Why:** Certain markets (electricity, power futures, interest rate instruments) may have negative prices.

## 8.2. Pricing Terminology
**R-8.2.1** Do not use the term "mark price" anywhere in this codebase (code, docs, comments, logs, or tests). Use "last price" instead.

```python
# ✅ Good
last_price = get_last_price(instrument)

# ❌ Bad
mark_price = get_mark_price(instrument)
```

## 8.3. Broker and SimBroker Semantics

**Core rules:**
- **R-8.3.1** One `Broker` instance (like `SimBroker`) represents one logical trading account
- **R-8.3.2** Account-level data (cash, margin, positions, open orders) must never mix multiple accounts inside a single Broker instance
- **R-8.3.3** Multiple accounts are modelled by multiple Broker instances added to a `TradingEngine` via `add_broker(name, broker)`

**SimBroker usage:**
- **R-8.3.4** A `SimBroker` instance holds state for exactly one simulated account
- **R-8.3.5** To simulate multiple accounts, create multiple `SimBroker` instances and register them under different names
- **R-8.3.6** Strategies that share a `SimBroker` share one simulated account; strategies wired to different `SimBroker` instances are account-isolated

**Responsibilities split:**
- **R-8.3.7** Brokers simulate realistic order lifecycle, order fills, margin, and fee handling for their account
- **R-8.3.8** `TradingEngine` records order fills per Strategy and provides the raw data for backtest statistics
- **R-8.3.9** Reporting utilities should reconstruct per-Strategy and portfolio metrics from order fills and positions instead of embedding reporting into Broker implementations

**Acceptance checks:**
- [ ] R-8.1.1: Generic validators allow negative prices where market supports them

---

# 9. Testing Guidelines

- **R-9.0.1** Do not automatically run tests; the maintainer will run tests manually to save tokens/resources
- **R-9.0.2** Do not generate tests unless explicitly asked
- **R-9.0.3** Use **pytest** (not unittest)
- **R-9.0.4** Test function names start with `test_` and describe what they test
- **R-9.0.5** Organize: `tests/unit/` and `tests/integration/`
- **R-9.0.6** Mirror package structure of code under test
- **R-9.0.7** Keep only root `tests/__init__.py` file

## 9.1. Choosing Test Location and Package

**R-9.1.1** Place new tests based on what they exercise:

- **`tests/unit/`**: Test focuses on a single component or a very small group of closely related functions or classes. These tests should run fast, use simple fixtures, and avoid real I/O
- **`tests/integration/`**: Test covers multiple layers or components working together, or relies on realistic scenarios, external boundaries, or non-trivial I/O

**R-9.1.2** Choose the most specific and representative package under `tests/` so that the test path mirrors the production module it covers.

**R-9.1.3** Avoid dumping unrelated tests into generic modules such as `tests/unit/test_misc.py`.

**R-9.1.4** If in doubt, start in `tests/unit/`. Move or duplicate the scenario into `tests/integration/` only when it clearly spans several layers.

## 9.2. Use DataGenerationAssistant (`DGA`) for Test Data

**R-9.2.1** Use the shared `DataGenerationAssistant` (`DGA`) from `suite_trading.utils.data_generation.assistant` for creating common domain objects in tests and examples.

The `DataGenerationAssistant` is a lightweight, stateless entry point that exposes small factory namespaces. Each call creates fresh objects, so there is no shared mutable state between tests.

**Currently provides:**
- `instrument`: Helpers for creating `Instrument` fixtures
- `bar`: Helpers for creating single bars and bar series
- `order_book`: Helpers for creating simple `OrderBook` snapshots
- `trade_tick`: Helpers for creating trade ticks and series
- `quote_tick`: Helpers for creating quote ticks and series
- `pattern`: Helpers for scalar price patterns (linear, sine wave, zig-zag)

**Preferred import pattern:**
```python
from suite_trading.utils.data_generation.assistant import DGA


def test_example_instrument():
    instrument = DGA.instrument.future_es()
    # use $instrument in your test logic here
```

---

# 10. Git Commit Guidelines

## 10.1. Critical Rule
**R-10.1.1** Never auto-commit: Do not create commits, tags, or pushes unless explicitly requested by user in current message.

## 10.2. Commit Format
- **R-10.2.1** Imperative mood (command form): ✅ "Add user auth"; ❌ "Added user auth"
- **R-10.2.2** Subject line: ≤50 chars, capital letter, no period at end
- **R-10.2.3** Use present tense imperative verbs: Add, Fix, Remove, Update
- **R-10.2.4** Be descriptive about what and why
- **R-10.2.5** For longer commits: add body separated by blank line

---

# 11. Plan & Code Change Visualization

**R-11.0.1** When proposing changes, show per-file Before/After snippets with minimal unique context.
Use fenced code blocks, keep lines ≤150 chars, include acceptance checks, update imports.

**R-11.0.2** For workflow/pipeline refactors, also include a `Validate` → `Compute` → `Decide` → `Act` ASCII diagram (see R-4.5.8).

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
