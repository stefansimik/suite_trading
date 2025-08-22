# Suite Trading Framework — FAQ

This FAQ answers common conceptual questions about how the framework works. It focuses on
ideas and workflows, not code. Lines are wrapped to keep text readable.

## How do I get historical bars?

- In this framework, you request any data by adding an EventFeed to your Strategy.
- EventFeed is the generic mechanism that delivers events (including bars) into the engine.
- The engine merges events from all EventFeed(s) in chronological order so your Strategy
  receives a clean, time-ordered stream.

## What is an EventFeed?

- EventFeed is a single-responsibility provider that outputs events in chronological order.
- It exposes a simple protocol (peek, pop, is_finished, close, remove_events_before) so the
  engine can coordinate multiple feeds deterministically.
- You can plug in any data source by implementing an EventFeed that converts source records
  into domain events (for example, NewBarEvent for bars).

## Can I load bars from CSV? Where does the data live?

- Yes. Load your CSV into a pandas DataFrame with columns: start_dt, end_dt, open, high, low,
  close (volume optional). Ensure the DataFrame is sorted by end_dt (ascending). Then create
  BarsFromDataFrameEventFeed(df, bar_type) to stream NewBarEvent into your Strategy.
- Example in test: `uv run pytest tests/unit/suite_trading/platform/event_feed/bars_from_csv/test_bars_fom_csv.py`
- The framework is intentionally generic: you bring your own data via an EventFeed. You can
  adapt any source (CSV, database, API) as long as you construct the required DataFrame.

## How are bar time intervals defined? Do bars overlap?

- Bars use a left-closed, right-closed interval: [start_dt, end_dt], both endpoints
  inclusive. A bar ends exactly at its end_dt.
- Boundary rule: a tick with timestamp exactly equal to end_dt belongs to that closing bar
  and never to the next bar. No tick should ever be included in two bars.
- The framework does not force contiguous bars. Time gaps are allowed when your data source
  has gaps (for example, no trading activity or missing sessions).
- To prevent overlap, construct consecutive bars so that the next bar starts strictly after
  the previous bar’s end, or adopt a precise vendor convention. The engine accepts either as
  long as your EventFeed is consistent.
- See docs/bar-time-intervals.md for a detailed rationale for this convention.

## How do live and historical data differ conceptually?

- Both live and historical data are delivered as events via EventFeed(s).
- Historical feeds should mark events as historical to reflect that their arrival times
  derive from past data. Live feeds represent current, real-time market activity.
- Strategies can treat both uniformly, as the engine guarantees chronological processing.

## What is the mental model for EventFeed?

- Think “bring your own data” via EventFeed. Your Strategy adds one or more feeds, and
  the TradingEngine orchestrates them and delivers to individual Strategies in chronological order.

## Are gaps in data acceptable?

- Yes. The engine processes events strictly in chronological order but does not require that
  consecutive bars be contiguous. If your data has gaps, simply emit events for the bars you
  do have; the engine and Strategy will proceed correctly.

## Why prioritize EventFeed for everything?

- It provides a unified, composable abstraction for delivering any data / any events into the system.
- You can test Strategies by swapping feeds, replay history, or go live by switching the feed
  implementation, all without changing Strategy code.
