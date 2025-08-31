# Roadmap

A concise, high‑level plan for initial development. Phases are intentionally small and
focused. Last updated: 2025‑08‑31.

## Phase 0 — Bars from CSV/DataFrame — DONE ✅

Implemented via BarsFromDataFrameEventFeed.

## Phase 1 — Minute bar aggregation (core implemented) ✅

Status: Core resampling and aggregation are working end‑to‑end.

Implemented:
- MinuteBarResampler: N‑minute, day‑aligned (UTC), right‑closed windows; emits on window
  change/close; robust validations; partial vs full detection.
- MinuteBarAggregationEventFeed: EventFeed wrapper with peek/pop/is_finished/close/
  remove_events_before and listener API (add/remove/get_listeners). Integrates with
  TradingEngine via listeners after successful pop.
- Basic tests for 1‑>5 min aggregation, non‑zero start minute, missing minute inside a window,
  and first‑partial policy.
- FAQ updated to document EventFeed protocol including get_listeners().

Next tasks:
- Expand test matrix across windows: 5, 15, 20, 30, 60, 120, 240, 360, 720 (any divisor of 1440).
- Listener implementation: extract common listener registry (Mixin or helper) and reuse in
  EventFeed(s) (e.g., BarsFromDataFrameEventFeed, FixedSequenceEventFeed, PeriodicTimeEventFeed).
- Output bar type promotion: when window is a whole hour (60, 120, ...), optionally produce
  hourly bar units if supported by the domain model (keep minute unit as default for now).
- Naming: keep MinuteBarAggregationEventFeed; consider a generic TimeAggregationEventFeed only
  if/when seconds or non‑minute inputs are added.
- Document timezone alignment and window semantics in docs with short examples.

## Phase 2 — Indicators

Goal: Provide a minimal, composable indicator layer that consumes Event(s) and emits new
Event(s) without coupling to storage.

Scope examples:
- Moving averages (SMA/EMA), rolling metrics, crossovers
- Windowed computations keyed by instrument

Success criteria:
- Clear indicator API and examples; easy to plug into a Strategy without engine changes

## Phase 3 — Data adapters and file formats

Goal: Extend data ingestion beyond the basic CSV/DataFrame feed.

Scope examples:
- Support alternative CSV schemas via mappers
- Optional Parquet adapter for bars
- Pluggable datetime parsing strategies

Success criteria:
- Clear extension points without complicating Phase 0 API

## Phase 4 — SimulatedBroker

Goal: Minimal broker for order submission, fills, and positions to enable backtests.

Success criteria:
- Deterministic fills and clock; simple latency/fees hooks; integrates with Strategy/Engine

## Phase 5 — Performance analytics

Goal: Compute trade/portfolio stats over backtests with simple, dependency‑light outputs.

Success criteria:
- Basic returns and drawdown metrics; easy to export to CSV or plot

## Phase 6 — Visualization tooling

Goal: Provide simple, practical visualization for bars and trades to speed up inspection and
strategy debugging.

Scope examples:
- Minimal plotting utility (Matplotlib/Plotly) to render bars with entry/exit markers
- Example notebook/script showing how to visualize a backtest result
- Optional hooks to export events for external viewers; keep core code decoupled

Success criteria:
- One‑liner helper to render a Strategy's bar/trade timeline for a small dataset
- Clear, documented example in README/docs; no heavy dependencies or complex setup
- Non‑intrusive design that can be skipped by users who do not need visualization
