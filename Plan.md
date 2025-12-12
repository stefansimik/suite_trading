Active tasks (not implemented yet)

1) Stop-like orders (tests)
- Add simple integration tests for StopOrder with SimBroker (arm trigger -> trigger -> fill).
- Add simple integration tests for StopLimitOrder with SimBroker (arm trigger -> trigger -> fill).

2) Time-in-force (implementation + tests)
- Implement TimeInForce semantics in SimBroker (IOC, FOK, DAY, GTD, GTC).
- Add simple tests for each TimeInForce rule.
- If GTD is required, add a way to represent the good-till datetime on the order model.

3) Order relationships
- Implement OCO (one cancels other).
- Implement OUO and other relationships (define exact semantics first).

4) Account correctness review
- Review Account / SimAccount behavior for cash, margin blocking/releasing, and position lifecycle.

5) OrderBuilder
- Implement OrderBuilder for easy and safe order creation.

6) Indicators framework
- Implement an indicators framework (SMA, EMA, RSI, MACD, etc.).

7) Performance metrics
- Implement PerformanceStatistics per Strategy.

8) Streamlit export
- Export data for visualization: bars, executions, backtest results, equity curve.

9) Strategy regression / extensibility
- Test framework with more strategies and try to reproduce results of old strategies.
- Consider StrategyPlugin and/or Opportunity (+ plugins) only if it reduces duplication across multiple strategies.

10) Interactive Brokers
- Implement an InteractiveBrokers Broker.
