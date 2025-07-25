# Strategy Market Data Subscription and Order Execution Design

## Executive Summary

This document defines how:

* trading strategies request historical data + subscribe to live market data in a flexible and dynamic way
* and how orders are submitted in our algorithmic trading framework

The goal is to create a unified approach that works seamlessly for 3 main scenarios:

* backtesting (historical data + orders submitted to SimulatedBroker)
* paper trading (live data + orders submitted to SimulatedBroker)
* and live trading scenarios (live data + orders submitted to RealBroker)

## Core Design Requirements

### Requirement 1: Data Source Transparency
**The system must ensure that strategies remain agnostic to market data sources
and receive data through consistent interfaces.**

- Strategies must not depend on specific data provider implementations
- All market data must be delivered through standardized interfaces regardless of source
- Data format and structure must be consistent across all providers

We should design protocol named: `MarketDataProvider`, which contains the following interface methods:

**Connection Management:**
- `connect() -> None` - Establish market data provider connection
- `disconnect() -> None` - Close market data provider connection
- `is_connected() -> bool` - Check market data provider connection status

**Data Retrieval Methods:**
- `get_historical_bars_series(bar_type: BarType, from_dt: datetime, until_dt: Optional[datetime] = None) -> Sequence[Bar]`
- `stream_historical_bars(bar_type: BarType, from_dt: datetime, until_dt: Optional[datetime] = None) -> None`
- `subscribe_to_live_bars(bar_type: BarType) -> None`
- `subscribe_to_live_bars_with_history(bar_type: BarType, history_days: int) -> None`
- `unsubscribe_from_live_bars(bar_type: BarType) -> None`

### Requirement 2: Explicit Broker Selection
**The system must provide strategies with full control over broker selection through explicit broker specification
in the `Strategy.submit_order` method.**

- **Multiple Broker Support**: The system must support multiple brokers simultaneously:
  - `broker.SIM` → SimulatedBroker (default - this broker is natural part of the library and always present)
  - `broker.IB` → Interactive Brokers (planned real broker)
  - `broker.OANDA` → OANDA broker (example real only)
  - Additional brokers can be added as needed

- **Flexible Order Routing**: The system must allow strategies to decide execution destination via `submit_order(order, broker=broker.SIM)` method:
  - Complete flexibility to send any order to any broker at any time
  - Enable advanced strategies like arbitrage between brokers
  - Support all 3 scenarios: backtesting + paper trading + live trading within the same strategy

### Requirement 3: Instrument Flexibility
**The system must allow strategies to be configurable for different instruments and markets.**

- The same strategy must be able to run on different instruments like EUR/USD, GBP/USD and execute the same algorithm on various markets without code changes
- The system must support 2 most common patterns:
  - Instrument selection must be configurable through constructor parameters or some `StrategyConfig` object
  - Strategies must be able to implement **custom logic** for instrument selection (screening, random selection, etc.)

### Requirement 4: MarketDataProvider Interface
**The system must provide a unified MarketDataProvider interface that handles both historical and live market data with seamless integration.**

The system will have a single `MarketDataProvider` that supports all market data operations through intuitive,
user-friendly functions. This unified approach eliminates complexity and provides strategies with simple,
predictable access to market data.

#### Core MarketDataProvider Functions

The `MarketDataProvider` must provide these essential functions for bar data:

**1. Request Historical Bars (Two Forms)**
- **`get_historical_bars_series(bar_type, from_dt, until_dt=None)`**:
  - Returns complete historical dataset as a sequence, perfect for setting up indicators, calculating initial values, or analyzing patterns that need the full dataset available immediately
  - Useful for strategy initialization, indicator setup, and analysis requiring complete datasets
  - Specific callback function will be designed to handle the complete series delivery (like `Strategy.on_historical_bars_series`, but maybe we can figure out better names)
  - Memory-efficient for smaller datasets and initialization scenarios

- **`stream_historical_bars(bar_type, from_dt, until_dt=None)`**:
  - Delivers bars individually through callbacks, perfect for processing large historical datasets without loading everything into memory at once
  - Maintains chronological order just like live trading scenarios
  - Useful for backtesting and scenarios requiring large datasets without memory overhead
  - Enables processing of extensive historical data without loading everything into memory

**2. Subscribe to Live Bars**
- **`subscribe_to_live_bars(bar_type)`**:
  - Starts receiving live market data as it happens, allowing strategies to react to current market conditions
  - Can be called dynamically during strategy execution to adapt data needs based on runtime conditions
  - Delivers live bars through `Strategy.on_bar(bar, is_historical=False)` callback
  - Supports dynamic subscription during strategy execution
  - Of course, the opposite function for unsubscription must exist as well.

**3. Subscribe to Live Bars with History**
- **`subscribe_to_live_bars_with_history(bar_type, history_days)`**:
  - First feeds historical bars for the specified number of days before now, then automatically starts feeding live bars without any gaps between historical and live data
  - This ensures continuous data flow with no missing bars, critical for live trading scenarios that need recent historical context
  - Special method that provides seamless transition from historical to live data
  - Critical for live trading scenarios requiring initialization with recent historical context
  - Of course, the opposite function for unsubscription must exist as well.

#### Key Design Principles

**Parameters for All Functions:**
- **Bar Type**: The bar type specifying instrument and bar characteristics (contains both the financial instrument and bar specifications like timeframe, price type, etc.)
- **From DateTime**: Start datetime for historical data period
- **Until DateTime** (optional): End datetime (if not specified, means "until data available")
- **History Days**: Number of days before now to include historical data (for `subscribe_to_live_bars_with_history`)

**Dynamic Request Capability:**
- All data requests can be made dynamically at any moment during strategy execution
- Not limited to startup or initialization phases
- Enables sophisticated strategies that adapt data requirements based on market conditions
- Supports complex trading logic that requires historical context at decision points

**Chronological Data Integrity:**
- All streamed data must maintain chronological order consistent with live trading scenarios
- Future implementation will include validation components to ensure data ordering
- Critical for strategy reliability and realistic backtesting results

#### Future Extensions

This MarketDataProvider design starts with bar data and can be extended to support:
- Trade tick data with similar function patterns
- Quote tick data with corresponding methods
- Other market data types following the same logical structure

The function names and callback patterns established for bars will serve as templates for extending
to other data types, ensuring consistency across the entire market data interface.

## 3 supported trading scenarios

### Backtesting Scenario
- **Use Case**: Strategy development, optimization, performance analysis
- **Data**: Strategy uses historical market data only
- **Broker**: Orders will be sent to `SimulatedBroker` via `submit_order(order, broker=broker.SIM)`

### Paper Trading Scenario
- **Use Case**: Strategy validation with live data without financial risk
- **Data**: Strategy uses live market data feed
- **Broker**: Orders will be sent to `SimulatedBroker` via `submit_order(order, broker=broker.SIM)`

### Live Trading Scenario
- **Use Case**: Production trading with real money, arbitrage strategies, multi-broker execution
- **Data**: Strategy uses historical initialization data + live market data feed
- **Broker**: Strategy has full flexibility to choose broker:
  - Can send orders to `SimulatedBroker` via `submit_order(order, broker=broker.SIM)`
  - Can send orders to real brokers via `submit_order(order, broker=broker.IB)` or `submit_order(order, broker=broker.OANDA)`
  - Can mix different brokers for different orders within the same strategy

## Strategy Examples

### Example 1: Pure Backtesting Strategy
```python
# Data Requirements:
# - 1-minute bars for EUR/USD
# - Period: January 1, 2001 to December 31, 2001
# - Orders sent to SimulatedBroker

class MovingAverageCrossover(Strategy):
    def on_bar(self, bar, is_historical=True):
        if self.should_buy():
            order = self.create_buy_order()
            self.submit_order(order, broker=broker.SIM)  # Backtesting with SimulatedBroker
```

### Example 2: Paper Trading Strategy
```python
# Data Requirements:
# - 1-minute bars for EUR/USD
# - Historical: 30 days before current time
# - Live: Real-time 1-minute bars
# - All orders go to SimulatedBroker for paper trading
#
# Key Point: Paper trading means SimulatedBroker is used regardless of whether
# historical or live bars are coming. This is the essence of paper trading -
# processing live market data through SimulatedBroker for risk-free validation.
# (Historical data logically always goes to SimulatedBroker anyway)

class MovingAverageCrossover(Strategy):
    def on_bar(self, bar, is_historical=True):
        if self.should_buy():
            order = self.create_buy_order()
            # Always use SimulatedBroker for paper trading regardless of data type
            self.submit_order(order, broker=broker.SIM)  # Paper trading
```

### Example 3: Live Trading Strategy
```python
# Data Requirements:
# - 1-minute bars for EUR/USD
# - Historical: 30 days for initialization
# - Live: Real-time bars for trading
# - Strategy chooses broker based on data type and trading logic

class MovingAverageCrossover(Strategy):
    def on_bar(self, bar, is_historical=True):
        if self.should_buy():
            order = self.create_buy_order()
            if is_historical:
                # Historical data - typically use SimulatedBroker
                self.submit_order(order, broker=broker.SIM)
            else:
                # Live data - use real broker for live trading
                self.submit_order(order, broker=broker.IB)
```

### Example 4: Time-Based Live Strategy
```python
# Data Requirements:
# - 1-minute bars for EUR/USD
# - Historical: None needed
# - Live: Real-time bars for timing only
# - Logic: Execute trade at 14:30 daily

class TimeBasedStrategy(Strategy):
    def on_bar(self, bar, is_historical=True):
        if bar.timestamp.time() == time(14, 30):
            order = self.create_buy_order()
            # Send to IB broker for live trading
            self.submit_order(order, broker=broker.IB)
```

### Example 5: Multi-Broker Arbitrage Strategy
```python
# Data Requirements:
# - 1-minute bars for EUR/USD from multiple sources
# - Historical: 30 days for both brokers
# - Live: Real-time bars for arbitrage opportunities

class ArbitrageStrategy(Strategy):
    def on_bar(self, bar, is_historical=True):
        if self.should_arbitrage():
            buy_order = self.create_buy_order()
            sell_order = self.create_sell_order()

            if not is_historical:
                # Send orders to different brokers for arbitrage
                self.submit_order(buy_order, broker=broker.IB)      # Buy on IB
                self.submit_order(sell_order, broker=broker.OANDA)  # Sell on OANDA
```

### Example 6: Signal-Driven Strategy
```python
# Initial State: No market data subscriptions
# Runtime Behavior:
# 1. Monitors external signals (e.g., social media, news)
# 2. When signal detected for specific instrument:
#    - Requests 10 days of historical data
#    - Subscribes to live data feed
#    - Performs technical analysis and trading
# 3. Can unsubscribe and reset when signal ends
# 4. Returns to monitoring state

class SignalDrivenStrategy(Strategy):
    def on_signal(self, signal):
        if signal.strength > threshold:
            # Note: These method invocations are just conceptual -
            # real method names are to be designed yet
            self.request_historical_data(signal.instrument, days=10)
            self.subscribe_to_live_data(signal.instrument)

    def on_bar(self, bar, is_historical=True):
        if self.analysis_complete():
            order = self.create_order_from_analysis()

            # Choose broker based on instrument and market conditions
            if bar.instrument.symbol.startswith('EUR'):
                self.submit_order(order, broker=broker.IB)
            else:
                self.submit_order(order, broker=broker.OANDA)
```

## Architecture Requirements

### Strategy Interface
Strategies must provide methods to:
- **Request Market Data When Needed**:
  - Historical data (Dynamic Request: Request new data during runtime)
  - Live data (Dynamic Subscription: Request new data subscriptions during runtime)
- **Handle Data Events**: Process incoming historical and live market data in chronological order with data type awareness:
  - `on_bar(self, bar, is_historical=True)`: Process bar data with historical/live context
  - `on_trade_tick(self, tick, is_historical=True)`: Process trade tick data with historical/live context
  - `on_quote_tick(self, tick, is_historical=True)`: Process quote tick data with historical/live context
- **Submit Orders**: Use `submit_order(order, broker=broker.SIM)` method with explicit broker selection:
  - `broker=broker.SIM` (default): Routes to SimulatedBroker
  - `broker=broker.IB`: Routes to Interactive Brokers
  - `broker=broker.OANDA`: Routes to OANDA broker
  - Full flexibility to send any order to any available broker

### Trading Engine Capabilities
The TradingEngine must:
- **Route Data Requests**: Forward strategy data requests to appropriate provider(s)
- **Manage Subscriptions**: Track active subscriptions for each strategy
- **Ensure Data Continuity**: In live-trading mode, there should be no gap between historical vs. live data
- **Handle Multiple Strategies**: Support concurrent strategies with different data needs
- **Market Data Distribution**: Use MessageBus to deliver data to subscribed strategies with proper data type context (`is_historical` flag). The `NewBarEvent` class has been enhanced with an `is_historical` attribute to support this functionality. When creating NewBarEvent instances, the system must properly set the `is_historical` flag based on the data source (True for historical data, False for live data).
- **Broker Registration and Management**: TradingEngine should be able to add/register one or more brokers under specific custom names:
  - Each broker must be an instance of Broker protocol with the following interface:
    - `connect()` - Establish broker connection
    - `disconnect()` - Close broker connection
    - `is_connected()` - Check connection status
    - `submit_order(order: Order)` - Submit order for execution
    - `cancel_order(order: Order)` - Cancel an existing order
    - `modify_order(order: Order)` - Modify an existing order
    - `get_active_orders()` - Get all currently active orders
  - Support dynamic broker registration during runtime
  - Maintain a broker registry with named access (broker.SIM, broker.IB, broker.OANDA, etc.)
  - Route orders to specified brokers based on explicit broker selection from strategies

### Broker Architecture
- **SimulatedBroker (broker.SIM)**: Available for all scenarios (backtesting, paper trading, live trading simulation)
- **Multiple Real Broker Support**: The system supports multiple real broker instances simultaneously:
  - **Interactive Brokers (broker.IB)**: For IB connectivity
  - **OANDA (broker.OANDA)**: For OANDA connectivity
  - **Extensible Design**: Additional brokers can be added as needed
- **Broker Registry**: Named broker access through a centralized registry system
- **Unified Interface**: All brokers implement the same interface for consistent order handling
- **Independent Operation**: Each broker operates independently, allowing for:
  - Arbitrage strategies across brokers
  - Risk diversification
  - Broker-specific optimizations

## Importance of knowing, if data are historical or live:

Example:
`Strategy.on_bar(bar, is_historical=True/False)`

### Purpose and Benefits

The `Strategy.on_bar(bar, is_historical=True/False)` callback is a core component that provides strategies
with essential context about the nature of incoming market data. The `is_historical` parameter serves as a critical
decision-making tool that enables strategies to distinguish between different data contexts and make appropriate broker
selection decisions.

### Why the `is_historical` Parameter is Essential

**Context Awareness for Broker Selection:**
The `is_historical` parameter allows strategies to understand whether the incoming bar data represents:
- **Historical data** (`is_historical=True`): Data from the past, typically used for strategy initialization, backtesting, or analysis
- **Live data** (`is_historical=False`): Real-time market data that represents current market conditions

**Trading Mode Decision Making:**
This context awareness enables strategies to make intelligent decisions about order routing:

- **Paper Trading Mode**: When strategies receive live data (`is_historical=False`) but want to practice without financial risk, they can route orders to `SimulatedBroker` regardless of data type
- **Live Trading Mode**: When strategies receive live data (`is_historical=False`) and want to execute real trades, they can route orders to real brokers like `broker.IB` or `broker.OANDA`
- **Backtesting Mode**: When strategies receive historical data (`is_historical=True`), they typically route orders to `SimulatedBroker` for analysis purposes

### Practical Implementation Examples

```python
class SmartTradingStrategy(Strategy):
    def on_bar(self, bar, is_historical=True):
        if self.should_buy():
            order = self.create_buy_order()

            if is_historical:
                # Historical data - always use SimulatedBroker for analysis
                self.submit_order(order, broker=broker.SIM)
            else:
                # Live data - choose based on trading mode
                if self.paper_trading_mode:
                    # Paper trading: live data but simulated execution
                    self.submit_order(order, broker=broker.SIM)
                else:
                    # Live trading: live data with real execution
                    self.submit_order(order, broker=broker.IB)
```

This design pattern ensures that strategies can seamlessly transition between different trading modes while maintaining full control over execution destinations based on data context.

## NewBarEvent Implementation Details

To support the `is_historical` parameter functionality described above, the `NewBarEvent` class has been enhanced with the following implementation:

### Updated Constructor
```python
def __init__(self,
             bar: Bar,
             dt_received: datetime,
             is_historical: bool = True):
```

### New Property
```python
@property
def is_historical(self) -> bool:
    """Get whether this bar data is historical or live."""
    return self._is_historical
```

### Integration Points
- **Historical data requests**: Create NewBarEvent with `is_historical=True`
- **Live data feeds**: Create NewBarEvent with `is_historical=False`
- **Strategy event handling**: Extract `is_historical` from NewBarEvent for callback context
- **MessageBus distribution**: TradingEngine uses MessageBus to route events to appropriate strategy subscribers with proper historical context

This enhancement ensures that all bar data events carry the necessary context information to enable intelligent broker selection and trading mode decisions within strategies.
