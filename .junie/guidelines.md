# Junie Guidelines (LLM-optimized)

Project: Modern algorithmic trading framework in Python for backtesting and live trading.

# Table of contents
1. Golden rules and priorities
   1. Core principles
   2. Initial development mode
   3. User‑centric API design
2. Code writing rules (critical)
   1. Naming
   2. Standard classes only
   3. Parameter formatting
   4. String interpolation and logging
   5. String representation methods
   6. Documentation (docstrings)
   7. Comments (format, content, narrative, "# Check:")
   8. Exception messages
   9. Markdown formatting
3. Code organization (supporting)
   1. Regions
   2. Imports and package structure
4. Testing guidelines
5. Git commit guidelines
6. Plan and code change visualization (Before/After template)

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
Rule: During initial development, ignore historical and backwards compatibility.

Why this matters now:
- Any functionality can be removed and replaced with better implementations
- Breaking changes are allowed; no deprecation or migration required
- APIs can be redesigned without keeping old interfaces
- No backwards compatibility guarantees
- Focus on getting it right over preserving legacy code

## 1.3 User‑centric API design
Rule: Design APIs for the user, not for internal convenience.

Decision framework:
1. Identify user mental model (how users think about it)
2. Assess implementation cost (is the user‑friendly approach expensive?)
3. Consider consistency (does it fit existing APIs?)
4. Evaluate maintenance (will it create ongoing complexity?)
5. Balance principles (how it interacts with KISS/YAGNI/DRY)

Rule of thumb: If cost is low and user benefit is clear, prefer the user‑centric approach.

# 2. Code writing rules (critical)

## 2.1 Naming
Rule: Names must be simple, predictable, and self‑documenting.

Guidelines:
- Use clear, descriptive names
- Avoid abbreviations (use `user_count`, not `usr_cnt`)
- Use verbs for functions (`calculate_total`, `send_message`)
- Use nouns for variables (`total_amount`, `user_list`)
- Be specific (`trading_engine` over `engine`; `bar_data` over `data`)
- Follow Python conventions (snake_case for functions/variables)

Examples:
```python
# ✅ Good
def calculate_portfolio_value(positions: list) -> Decimal:
    total_value = Decimal('0')
    for position in positions:
        market_price = get_current_price(position.instrument)
        position_value = position.quantity * market_price
        total_value += position_value
    return total_value

# ❌ Bad
def calc_pv(pos: list) -> Decimal:
    tv = Decimal('0')
    for p in pos:
        mp = get_price(p.inst)
        pv = p.qty * mp
        tv += pv
    return tv
```

## 2.2 Standard classes only
Rule: Use standard classes exclusively. No dataclasses allowed.

Why:
- KISS: One pattern everywhere; nothing special to remember
- Explicit over implicit: Initialization and validation are visible
- Predictable, consistent behavior across all domain objects

## 2.3 Parameter formatting
- Put each parameter on its own line for long signatures (functions, methods, constructors)
- Keep indentation consistent
- Add a trailing comma in multi‑line parameter lists
- Align and space long function names properly

Examples:
```python
# ❌ Wrong
def __init__(self, instrument: Instrument, side: OrderDirection, quantity: Decimal,
             order_id: int = None) -> None:

# ✅ Good
def __init__(
    self,
    instrument: Instrument,
    side: OrderDirection,
    quantity: Decimal,
    order_id: int = None,
) -> None:

# ✅ Good
def get_historical_bars_series(
    self,
    instrument: Instrument,
    from_dt: datetime,
    until_dt: Optional[datetime] = None,
) -> Sequence[Bar]:
    ...
```

## 2.4 String interpolation and logging
Rule: Always use f‑strings. Never use old‑style interpolation or logger format args.
- Applies everywhere: logs, exceptions, messages, general strings

Allowed:
- `logger.info(f"Started strategy '{name}'")`
- Plain constant strings when no interpolation is needed

Forbidden:
- `logger.info("Started strategy '%s'", name)`
- `logger.info("Started strategy '{}'".format(name))`
- `"Hello, %s" % name`

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

## 2.6 Documentation (docstrings)
- Use Google style
- Put content on separate lines
- Include purpose, parameters, return values, exceptions
- Include types for all params, returns, and attributes

Docstring writing style:
- Use natural language (explain to a colleague)
- Use simple words
- Write for beginners; explain concepts clearly
- Make benefits concrete (what it does and why it matters)

Examples of phrasing:
- ✅ "Engine makes sure the provider is available"
- ✅ "Simple way to get events from different sources"

## 2.7 Comments (format, content, narrative, "# Check:")

Formatting:
- Exactly 2 spaces before `#` for inline comments; align within the block
- Use sentence case for section comments

Example:
```python
# Order identification
order_id: str  # Unique identifier for the order
side: OrderDirection  # Whether this is a BUY or SELL order
```

Content rules:
- Use domain names and exact states (TradingEngine, Strategy, NEW/ADDED/RUNNING/STOPPED/ERROR)
- Prefer positive, action‑oriented phrasing
- Avoid meta comments about "who calls this" unless actionable for the user
- Add short intent comments when wiring/delegating (e.g., "Delegate to TradingEngine")
- Briefly note defaulting behavior when applying defaults

Narrative code comments:
Rule: Every small block (2–15 lines) gets a short conversational comment explaining the why/what.

Coverage:
- One block comment can cover multiple lines if they belong together
- Very small functions can be summarized by one block comment
- Long functions: split into logical blocks (or regions) and comment each

Formatting:
- Place the block comment directly above the code
- Use 1–3 short lines; max 100 chars per line
- Use normal comments for narrative; reserve "# Check:" only for guards

Content:
- Explain intent (why) and outcome (what)
- Use domain terms and state constants
- Interpret the code rather than restating it

Granularity guidance:
- Loops: describe what the loop achieves
- Branches: describe the decision purpose above the if/elif/else
- External calls: explain why you delegate (e.g., "Ask Broker to place order")

Examples:
```python
# Collect fills since last event and convert them into a single net order we can send now
fills = broker.get_fills_since(self._last_event_time)
net_qty = sum(fill.qty for fill in fills)
if net_qty == 0:
    return

# Send the order and record when we did it so the strategy timeline stays accurate
order = Order(instrument, side, net_qty)
broker.submit(order)
self._last_order_time = now()
```

Bad example:
```python
# Submit order
net_qty = sum(f.qty for f in fills)  #  sum quantities
order = Order(instrument, side, net_qty)  #  Create order
broker.submit(order)  #  Submit
```

Review checklist:
- Narrative comment above each logical block
- Comments read like plain English and explain intent
- Defensive checks have a single "# Check:" line above the guard
- Inline comments use 2 spaces before `#`; lines stay <= 100 chars
- Remove or update outdated/misleading comments

Defensive checks comments ("# Check:"):
Rule: Put one concise comment immediately before every defensive check.

What counts:
- Input/state/None/config validation; try/except used only for validation; asserts as runtime guards

Style:
- Start with "# Check:"; be specific (<= 100 chars); imperative phrasing
- Place it right before the check; one line per independent check

Example:
```python
# Check: strategy must be registered
if name not in self._strategies:
    raise KeyError(
        f"Cannot call `start_strategy` because $name ('{name}') is not registered.",
    )
```

Where to apply:
- Constructors and validators (__init__, _validate, property setters)
- Orchestration (engine/strategy/provider/broker)
- Parsing/conversion
- Any fast‑fail function

Why: Makes intent obvious, supports Fail Fast, and keeps reviews unambiguous.

## 2.8 Exception messages
Rule: Messages must be 100% clear, use codebase terminology, and guide the fix.

Core principles:
1. 100% clarity; no ambiguity
2. Terminology consistency (e.g., "added to TradingEngine" not "registered")
3. Specify variable types (say "strategy name", not just "name")

Format requirements:
1) Function context: name in backticks, e.g., `` `start_strategy` ``
2) Variable identification: prefix with `$` and use actual variable names
   - ❌ `$execution_order_id` vs code uses `execution.order.id`
   - ✅ `$order_id`
   - ❌ `$self_id` vs code uses `self.id`
   - ✅ `$id`
   - ❌ `$trading_engine_instance` vs code uses `self._trading_engine`
   - ✅ `$_trading_engine`
   - ❌ `$strategy_state` vs code uses `self.state`
   - ✅ `$state`
3) Variable values: include actual values when useful
   - Use f‑strings: `f"$strategy_name ('{name}')"`
   - For objects, include identifiers: `f"$instrument ({instrument.symbol})"`
4) Root cause: state the failed condition using project terms
5) Solution guidance: provide actionable advice with method names

Examples:
```python
raise KeyError(
    f"Cannot call `start_strategy` because strategy name $name ('{name}') is not added to "
    f"this TradingEngine. Add the strategy using `add_strategy` first."
)

raise ValueError(
    f"EventFeedProvider with provider name $name ('{name}') is already added to this "
    f"TradingEngine. Choose a different name."
)

raise ValueError(f"$quantity must be >= 1, but provided value is: {quantity}")

raise ValueError(
    "Strategy validation failed:\n"
    "• $strategy_name cannot be empty\n"
    "• $strategy must be in NEW state"
)
```

## 2.9 Markdown formatting
Rule: Maximum line length is 100 characters for all generated Markdown (including code blocks).

Requirements:
- Hard limit: lines <= 100 chars
- Insert line breaks at natural points
- Code blocks, lists, and headers follow the same limit

Example:
```markdown
# ✅ Good
This paragraph stays within the 100‑character limit by breaking at natural points for readability.

# ❌ Bad
This paragraph exceeds the 100‑character limit and should be broken into multiple lines.
```

# 3. Code organization (supporting)

## 3.1 Regions
Rule: Use regions to structure large files and multi‑section classes.

Why: Clear separation of concerns; easier navigation; especially helpful for AI‑edited files.

When to use:
- Files with 100+ lines and multiple logical sections
- Classes with multiple responsibilities (engines, strategies, factories)
- Files with distinct groups (initialization, lifecycle, data handling, etc.)

Guidelines:
- Use simple names: "Initialize engine" over "Initialization Methods"
- Use verbs: "Start and stop engine", "Manage strategies", "Submit orders"
- Group related management regions (strategies, providers, brokers)
- Always mark with `# region [name]` and `# endregion`
- Re‑evaluate and update regions when editing

Example:
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

## 3.2 Imports and package structure

Import management after changes:
- After every code change, re‑check imports; remove obsolete, add missing

No re‑exports rule:
- Never re‑export from `__init__.py`
- Import classes/functions directly from their source modules

Benefits:
- Zero ambiguity: exactly one way to import each class
- Clear dependencies in import statements
- Zero maintenance of `__all__` lists or re‑exports
- IDE‑friendly (auto‑complete and Go to Definition work reliably)

Examples:
```python
# ✅ Good
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.order.order_enums import OrderSide

# ❌ Bad
from suite_trading import TradingEngine
from suite_trading.domain import Bar
```

Package structure and `__init__.py` files:
- Create `__init__.py` only for executable code, version info, or package initialization logic
- Do not create `__init__.py` that contains only docstrings/comments or is empty
- Prefer namespace packages (PEP 420) for directory organization (no `__init__.py`)

Examples:
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

# 4. Testing guidelines
- Do not generate tests unless explicitly asked
- Use pytest (not unittest)
- Test function names start with `test_` and describe what they test
- Organize tests in `tests/unit/` and `tests/integration/`
- Mirror the package structure of the code under test
- Keep only the root `tests/__init__.py` file

# 5. Git commit guidelines
- Write commits in imperative mood (command form)
  - ✅ "Add user authentication"; ❌ "Added user authentication"
- Subject line: <= 50 chars; start with a capital letter; no period at end
- Use present tense imperative verbs: Add, Fix, Remove, Update
- Be descriptive about what and why
- For longer commits, add a body separated by a blank line

# 6. Plan and code change visualization
Rule: When preparing implementation plan, show changes with clear Before/After snippets for every edited file and location.

Why: Visual diffs reduce ambiguity, speed up reviews, and make intent obvious.

Before/After visualization rules:
1) Start with a file header line:
   - File: path/to/file.py
2) Add a short one‑line context (optional but recommended)
3) Provide a minimal, unique Before snippet
4) Provide the exact After snippet

Formatting rules:
- Use fenced code blocks with language hints (python, text)
- Precede each code block with "Before:" or "After:"
- Keep snippets concise but uniquely identifiable
- Wrap lines at <= 100 chars
- When editing imports or docstrings, include only minimal necessary context
- For deletions only, show Before and then "After: (removed)"
- For additions only, show the closest anchor in Before, then show the added After block

Logging and comments:
- When logs are affected, show Before/After log lines
- When comments/docstrings change, include them in the snippets
- Respect comment formatting and docstring style rules

Minimal template:

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

Repeat the File/Before/After pattern for each touched file. Keep each code block under 100 chars.
Ensure imports are updated after changes.
