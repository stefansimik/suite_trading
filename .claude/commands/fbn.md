---
argument-hint: <name_of_the_thing>
description: Find best name
---

# Python Naming Assistant - Enhanced Prompt

```markdown
# Main Goal
Find the optimal name for: $ARGUMENTS

---

## Naming Requirements

### Core Principles
- **Simplicity**: Minimize length while maximizing clarity
  - Ideal: 1 word (e.g., `user`, `count`, `data`)
  - Acceptable: 2-3 words (e.g., `user_count`, `process_data`)
  - Maximum: 4 words (only for complex domain concepts)

- **Intuitiveness**: Instantly understandable to developers
  - No mental translation required
  - Purpose is self-evident from the name alone
  - Follows principle of least surprise

- **Descriptiveness**: Accurate representation of reality
  - Variables: What data is stored (type/content/purpose)
  - Functions: What action is performed or value is returned
  - Classes: What entity/concept is modeled
  - Constants: What fixed value represents

- **Convention Adherence**: Python PEP 8 compliance
  - Variables/functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
  - Private members: `_leading_underscore`
  - Avoid: single letters (except counters: i, j, k), abbreviations, Hungarian notation

### Context-Specific Guidelines

**For Variables:**
- Use nouns or noun phrases
- Be specific about data type when relevant (`user_list` vs `users`, `count` vs `total_count`)
- Avoid generic names (`data`, `temp`, `obj`, `thing`)

**For Functions:**
- Start with verbs for actions (`calculate`, `fetch`, `validate`, `process`)
- Use nouns/adjectives for predicates/getters (`is_valid`, `has_permission`, `user_email`)
- Boolean-returning functions: `is_`, `has_`, `can_`, `should_` prefixes

**For Classes:**
- Use singular nouns (`User`, not `Users`)
- Describe the abstraction, not implementation
- Avoid suffixes like `Manager`, `Handler`, `Helper` unless truly necessary

**For Loop Variables:**
- Singular form of the iterable (`for user in users`)
- Descriptive even in short loops (avoid bare `i` when `index` is clearer)

---

## Process Steps

### Step 1: Generate 30 High-Quality Candidates
- Consider the object type (variable/function/class/constant)
- Include variations with different specificity levels
- Mix short and longer descriptive options
- Account for context provided in $ARGUMENTS

### Step 2: Scoring System (1-10 scale)
Apply these weighted scores:
- **Intuitiveness** (weight: 4.0) - How quickly a developer understands purpose
- **Descriptiveness** (weight: 3.0) - How accurately it reflects reality
- **Simplicity** (weight: 2.0) - How concise without losing clarity

**Total Score = (Intuitiveness × 4.0) + (Descriptiveness × 3.0) + (Simplicity × 2.0)**

### Step 3: Results Table
Display ONE table sorted by **Total Score (descending)**:

| Rank | Name | Intuit. | Descrip. | Simple. | Total | Summary |
|------|------|---------|----------|---------|-------|---------|
| ... | ... | ... | ... | ... | ... | Brief pros/cons |

### Step 4: Final Recommendation

**If clear winner exists:**
- State the recommended name
- Explain why it's the best choice
- Mention any considerations for its use

**If multiple names tie for highest score:**
- Create **Tie-Breaker Analysis** section
- For each tied candidate, analyze:
  - Specific contexts where it excels
  - Potential ambiguities or edge cases
  - Common usage patterns in Python ecosystem
  - Risk of confusion with similar terms
  - Readability in typical code constructs
- **Declare the winner** with explicit justification

---

## Control Checklist

Before finalizing the recommendation, verify:

### ✓ Convention Compliance
- [ ] Follows PEP 8 naming conventions for the object type
- [ ] Uses correct case style (snake_case/PascalCase/UPPER_SNAKE_CASE)
- [ ] No prohibited patterns (mixedCase, Hungarian notation)

### ✓ Clarity & Understandability
- [ ] Name is self-explanatory without requiring context
- [ ] No ambiguous abbreviations or acronyms (unless universally known: HTTP, URL, ID)
- [ ] Pronunciation is natural and unambiguous
- [ ] Not easily confused with Python built-ins or common library names

### ✓ Specificity & Precision
- [ ] Accurately describes content/behavior/purpose
- [ ] Appropriate level of detail (neither too generic nor over-specified)
- [ ] Distinguishable from similar variables/functions in typical scope
- [ ] Type hints would complement (not contradict) the name

### ✓ Code Context Fit
- [ ] Reads naturally in common usage patterns:
  - For variables: `if name:`, `for item in name:`, `name.method()`
  - For functions: `result = name()`, `name(arg1, arg2)`
  - For classes: `instance = Name()`, `class Child(Name):`
- [ ] Length is proportional to scope (shorter for tight loops, longer for module-level)
- [ ] Works well with common method/attribute access patterns

### ✓ Maintainability
- [ ] Easy to search for in codebase (not too generic)
- [ ] Refactoring-friendly (clear semantic meaning)
- [ ] Scales well if similar names needed (`user` → `active_user`, `guest_user`)

### ✓ Anti-Pattern Avoidance
- [ ] Not a single letter (unless loop counter in trivial context)
- [ ] Not needlessly generic (`data`, `info`, `obj`, `temp`, `result` without context)
- [ ] Not redundant with type (`user_dict` when `users` is sufficient with type hints)
- [ ] Not using "manager/handler/helper" unless truly modeling that pattern
- [ ] Not mixing metaphors or combining unrelated concepts

### ✓ Final Validation
- [ ] Read aloud: Does it sound natural?
- [ ] Grep test: Will searching for this name find what you expect?
- [ ] Newcomer test: Would a new team member understand this without explanation?
- [ ] Future-proof: Will this still make sense if requirements evolve slightly?

---

## Output Format

```
# Naming Analysis for: [description of $ARGUMENTS]

## Generated Candidates (20)

[table with all candidates and scores]

## Final Recommendation

**Recommended Name:** `name_here`

**Rationale:**
[Clear explanation of why this is the best choice]

**Considerations:**
[Any important notes about using this name]

[If tie-breaker was needed, include that analysis here]
```
