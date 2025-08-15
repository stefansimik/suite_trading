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

## 2.2 Classes, dataclasses, and named tuples
Rule: Use standard classes for fundamental domain models. Dataclasses and named tuples are
allowed for simple config or helper/value objects.

Why:
- Core domain needs explicit initialization and validation.
- Dataclasses/named tuples can reduce boilerplate for auxiliary data without hiding intent.

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

Identify domain objects by name (instance) vs class (type)
- When referring to a specific instance: use "ClassName named '{name}'".
  - Examples: "Strategy named '{strategy_name}'", "EventFeed named '{feed_name}'".
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
- All logger calls must be on a single line, regardless of message length.

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


Length and clarity
- Do not wrap logger calls; a logger call must be one line even if >100 chars. Prefer concise wording.
- Prefer concrete, unambiguous wording; avoid pronouns like "it" when a named object exists.

Examples (Do/Don't)
- Do: `logger.info(f"Started Strategy named '{name}'")`
- Do: `logger.error(f"Error auto-stopping Strategy named '{name}': {e}")`
- Do: `logger.debug(f"Cleaned up finished EventFeed named '{feed_name}' for Strategy named '{s}'")`
- Don't: `logger.info(f"Started strategy '{name}'")`  # wrong casing/pattern
- Don't: `logger.debug("EventFeed '%s' removed", feed_name)`  # format args

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

Key principles:
- Use Google-style docstrings with purpose, params, returns, exceptions, and types
- Write in accessible language that any developer can understand
- Include all important information, but explain complex concepts simply
- Make it immediately understandable without additional research
- When needed, reference related code that provides essential context
- Use concrete examples when helpful

Focus: Formal documentation for functions, classes, and modules that other developers will use.

## 2.7 Code Comments (Narrative & Defensive)
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
