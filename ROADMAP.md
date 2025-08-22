# Roadmap

A clean, high-level plan for initial development. Phases are intentionally small and focused.

## Phase 1 — Bar aggregation

Goal: Create BarAggregatorEventFeed that consumes another EventFeed (emitting NewBarEvent) and
produces aggregated BarEvent(s).

Strategy must receive:
- Aggregated bars (e.g., 5-min bar)
- Individual source bars used to build the aggregate (e.g., original 1‑min bars)

Design options to evaluate:
- Connect both feeds via a MessageBus
- Instruct the original 1‑min feed to forward/copy individual bars to the aggregator
- Do aggregation inside Strategy (no BarAggregatorEventFeed)

Success criteria:
- Simple, generic, intuitive architecture that is easy to extend

---

## Phase 2 — Indicators

---

## Phase 3 — Data adapters and file formats

Goal: Extend data ingestion beyond the basic CSV feed.

Scope examples:
- Support alternative CSV schemas via mappers
- Optional Parquet adapter for bars
- Pluggable datetime parsing strategies

Success criteria:
- Clear extension points without complicating Phase 0 API

---

## Phase 4 — SimulatedBroker

---

## Phase 5 — Performance analytics

---

## Phase 6 — Visualization tooling

Goal: Provide simple, practical visualization for bars and trades to speed up inspection and
strategy debugging.

Scope examples:
- Minimal plotting utility (e.g., Matplotlib/Plotly) to render bars with entry/exit markers
- Example notebook or script showing how to visualize a backtest result
- Optional hooks to export events for external viewers; keep core code decoupled

Success criteria:
- One-line helper to render a Strategy's bar and trade timeline for a small dataset
- Clear, documented example in README/docs; no heavy dependencies or complex setup
- Non-intrusive design that can be skipped by users who do not need visualization
