# Roadmap

A concise, high‑level plan for initial development. Phases are intentionally small and
focused. Last updated: 2025‑08‑31.

## Phase 0 — Bars from CSV/DataFrame — DONE ✅

Implemented via BarsFromDataFrameEventFeed.

## Phase 1 — Minute bar aggregation (core implemented) ✅

1. Ak je agregovany bar nasobkom 60-minut, nastav vystupny bar ako hodinovy
2. Urob test pre dalsie resamplingy:
    - 1min bary -> 5-min, 15-min, 20-min, 30-min, 1-hour, 2-hour, 4-hour, 6-hour, 12-hour
    - 5-min bary -> 15-min, 30-min, 1-hour, 2-hour, 4-hour, 6-hour, 12-hour
    - 15-min bary -> 30-min, 1-hour, 2-hour, 4-hour, 6-hour, 12-hour
    - 30-min bary -> 1-hour, 2-hour, 4-hour, 6-hour, 12-hour
    - 1-hour bary -> 2-hour, 4-hour, 6-hour, 12-hour
3. Zanalyzuj, ako by sme mohli agregovat SECONDS bars
    * zrejme by sme nastavili opat X-nasobok do agregacie
    * a pri vystupe by stacilo agregovany bar zaokruhlit na sekundy/minuty/hod, podla toho akoby to vyslo
4. Dorobit aggregator pre Daily bars
5. Dorobit aggregator pre Weekly bars
6. Dorobit aggregator pre Monthly b
7. Dorobit aggregator pre VolumeBars

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
