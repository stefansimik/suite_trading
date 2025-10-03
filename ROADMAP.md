# Roadmap

A concise, high‑level plan for initial development. Phases are intentionally small and
focused. Last updated: 2025‑09‑14.

## Phase 0 — Bars from CSV/DataFrame — DONE ✅

Implemented via BarsFromDataFrameEventFeed.

## Phase 1 — Minute bar aggregation (core implemented) ✅

1. Emit hour-typed bars when target size is a multiple of 60 minutes — DONE ✅
2. Parametrized tests for resampling matrix across seconds/minutes/hours — DONE ✅
    - Single-boundary and five-interval tests validate behavior and types
    - Matrix covers bases: 1s, 5s, 1m, 5m, 15m, 30m, 1h
    - Matrix covers targets: 5s, 15s, 30s, 1m, 5m, 15m, 20m, 30m, 1h, 2h, 4h, 6h, 12h
3. Support seconds-based aggregation and boundary rounding — DONE ✅
4. Add Daily bar aggregation — DONE ✅
5. Add Weekly bar aggregation — DONE ✅
6. Add Monthly bar aggregation — DONE ✅
7. Add VolumeBar aggregation — TODO

   Volume bars are a special type of candlestick where each candle represents a constant traded
   volume instead of a constant time period. When aggregating from higher‑resolution data (for
   example tick‑by‑tick data) into volume bars, a problem can occur when source trades do not
   divide exactly into the requested fixed volume.

   Main approaches to address this problem:
   A) Exact Volume Matching:
    When the target volume (e.g., 1000 contracts) is reached exactly, the candle is closed.
    If the last trade exceeds the limit, split the trade — part goes to the current candle,
    the remainder starts a new one.
    Advantage: Every candle has exactly the same volume.
    Disadvantage: May split individual trades, which is not always realistic

   B) Overflow Method — RECOMMENDED WAY
    Add the entire trade that exceeds the limit to the current candle.
    The resulting volume bars have slightly different volumes (always ≥ the target).
    Advantage: Preserves the integrity of individual trades.
    Disadvantage: Inconsistent candle volumes

8. Bar aggregation should also accept TimeEvents, that would close and emit the bars, if no last finishing source bar comes.

9. Maybe part of Event interface should be `is_historical` or `is_live` flag.

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
