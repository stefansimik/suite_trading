# Junie Guidelines

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

Prefer user‑friendly choices when cost is low, they fit the existing style, and do not add
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

## 2.2 Standard classes only
Rule: Use standard classes exclusively. No dataclasses allowed.

Why:
- KISS: One pattern everywhere; nothing special to remember
- Explicit over implicit: Initialization and validation are visible
- Predictable, consistent behavior across all domain objects

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
Use Google‑style docstrings with purpose, params, returns, exceptions, and types.
Write in plain English for beginners.

## 2.7 Comments (format, content, narrative, "# Check:")

Comment rules:
- Inline: 2 spaces before #; sentence case for section comments.
- Narrative: Each 2–15 line block gets a short "why/what" comment above it.
- Use domain terms and explicit states.
- Reserve "# Check:" for defensive guards, placed immediately above the check.

Example narrative:
```python
# Collect fills since last event and net the quantity
fills = broker.get_fills_since(self._last_event_time)
net_qty = sum(f.qty for f in fills)
if net_qty == 0:
    return

# Send order and record time
broker.submit(Order(instrument, side, net_qty))
self._last_order_time = now()
```

Example defensive check:
```python
# Check: strategy must be added before start
if name not in self._strategies:
    raise KeyError(
        f"Cannot call `start_strategy` because $name ('{name}') is not added to this ",
        f"TradingEngine. Add it using `add_strategy` first."
    )
```

## 2.8 Exception messages
Exception messages checklist:
- 100% clear, use project terms, guide the fix.
- Include function name in backticks.
- Identify variables with $ and real names; include values when helpful.

Template:
```python
raise ValueError(
    f"Cannot call `start_strategy` because $state ('{self.state}') is not NEW. "
    f"Call `reset` or create a new Strategy."
)
```

## 2.9 Markdown formatting
Keep all Markdown lines (including code) <= 100 chars. Break lines at natural points.

# 3. Code organization (supporting)

## 3.1 Regions
Use regions to structure large files/classes. Name regions with verbs (e.g., "Manage
strategies"). Always mark with "# region ..." / "# endregion".

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
