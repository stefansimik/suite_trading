# Time-in-force (implementation + tests)
- Implement TimeInForce semantics in SimBroker (IOC, FOK, DAY, GTD, GTC).
- Add simple tests for each TimeInForce rule.
- If GTD is required, add a way to represent the good-till datetime on the order model.

# Order relationships
- Implement OCO (one cancels other).
- Implement OUO and other relationships (define exact semantics first).

# Account correctness review
- Review Account / SimAccount behavior for cash, margin blocking/releasing, and position lifecycle.

# OrderBuilder
- Implement OrderBuilder for easy and safe order creation.

# Indicators framework
- Implement an indicators framework (SMA, EMA, RSI, MACD, etc.).

# Performance metrics
- Implement PerformanceStatistics per Strategy.

# Streamlit export
- Export data for visualization: bars, executions, backtest results, equity curve.

# Strategy regression / extensibility
- Test framework with more strategies and try to reproduce results of old strategies.
- Consider StrategyPlugin and/or Opportunity (+ plugins) only if it reduces duplication across multiple strategies.

# Interactive Brokers
- Implement an InteractiveBrokers Broker.
