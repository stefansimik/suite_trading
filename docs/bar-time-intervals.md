# Bar Time Intervals Convention

This document explains the time interval convention used for bars in the trading framework.

## Overview

Bars use **LEFT-CLOSED, RIGHT-CLOSED** intervals `[start_dt, end_dt]`, meaning both the start and end timestamps are included in the bar period. For example, a 5-minute bar ending at 15:35:00 covers the period `[15:30:00, 15:35:00]`, including both boundary timestamps.

## Why Left-Closed, Right-Closed is Better

### 1. Real-World Data Collection

In practice, bars are built by accumulating ticks/trades over time:

```
15:30:00.000 ← Start collecting data
15:30:15.123 ← Trade occurs
15:31:42.456 ← Trade occurs
...
15:35:00.000 ← Stop collecting, close the bar
```

The bar naturally includes both the start moment (when collection begins) and the end moment (when collection stops). Excluding the start would mean losing the first tick that arrives exactly at the boundary.

### 2. Market Open/Close Alignment

Consider a daily bar for a market that opens at 09:30:00 and closes at 16:00:00.

- **With `[09:30:00, 16:00:00]`**: The bar captures the entire trading session including opening and closing auctions.
- **With `(09:30:00, 16:00:00]`**: You'd miss the opening tick at exactly 09:30:00, which is often crucial market data.

### 3. Historical Data Reconstruction

When reconstructing bars from tick data:

```python
# Left-closed, right-closed: Natural and inclusive
for tick in ticks:
    if bar.start_dt <= tick.timestamp <= bar.end_dt:
        bar.add_tick(tick)

# Left-open, right-closed: Awkward exclusion
for tick in ticks:
    if bar.start_dt < tick.timestamp <= bar.end_dt:
        bar.add_tick(tick)  # Loses ticks exactly at start_dt!
```

### 4. Continuous Time Series

In continuous markets (like forex), there's always activity. The "end" of one bar and "start" of the next happen simultaneously. The timestamp belongs to the closing bar by convention, making `[start, end]` natural.

### 5. Database and Storage Efficiency

Most time-series databases and storage systems are optimized for inclusive ranges. Queries like "give me all data from 15:30 to 15:35" naturally include both endpoints.

## The Overlap "Problem" is Actually Not a Problem

The apparent "overlap" in `[15:30, 15:35]` and `[15:35, 15:40]` is resolved by the temporal ordering rule:

- Any tick exactly at 15:35:00 belongs to the bar ending at 15:35
- The next bar starts immediately after (15:35:00.001 or next tick)

## Alternative Conventions

While **left-open, right-closed** `(start, end]` has mathematical elegance, **left-closed, right-closed** `[start, end]` wins because:

1. **Practical data collection** naturally includes both boundaries
2. **Market session alignment** captures complete trading periods
3. **Trader intuition**: "15:35 bar" should include data at 15:35
4. **System efficiency** in databases and time-series operations
5. **Historical precedent** in financial systems

The "overlap" issue is a theoretical concern that doesn't cause practical problems due to temporal ordering rules and the discrete nature of market data processing.
