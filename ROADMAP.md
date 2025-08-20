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

## Phase 3 — EventFeed for historical CSV data

---

## Phase 4 — SimulatedBroker

---

## Phase 5 — Performance analytics

---
