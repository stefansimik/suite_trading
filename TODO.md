### Implement as 1st things

#### 1.1 Clock System

Handling time consistently is one of the trickiest aspects of a unified trading system. In backtesting, time is a controllable simulation; in live trading, time is driven by the real world (exchange clock and wall-clock).

**Key Features:**
- **Unified Time Management**: Single clock interface for both backtesting and live-trading
- **Two Implementations Required:**
  - **RealtimeClock**: For live trading operations, provides current real time
  - **HistoricalClock**: For backtesting operations, allows controllable time simulation
    - Configurable - allows setting date/time to specific value in history
    - Allows advancing time by specified period
    - Advances based on next available market data (no fixed time resolution)

**Architecture Decisions:**
- Clock should be standalone component living inside TradingEngine
- TradingEngine will have both clocks available simultaneously:
  - HistoricalClock - for historical data processing
  - RealtimeClock - for live bars and live-trading
- Everything inside the framework processes in UTC timezone
- Time resolution is dynamic - HistoricalClock advances to next nearest market data timestamp

**Future Features (deferred):**
- One-time callbacks (at specific date/time)
- Scheduled recurring callbacks (every N seconds/minutes/hours)
- Callback cancellation capabilities

If a strategy uses multiple symbols or timeframes, the engine must synchronize them so that at each "tick" of the clock the strategy sees a coherent snapshot. Clock should advance time to the next market data with nearest timestamp across all data feeds.

#### 1.2 MarketDataStorage

**Note:** Renamed from MarketDataCatalog for clarity - this component is essentially market data storage.

MarketDataStorage should be an abstract storage interface (Protocol), allowing multiple implementations.

**Design Focus:**
- Primary goal is designing a good interface
- Should be conceptual Interface/Protocol/ABC class providing all required functions
- Multiple implementations possible:
  - SQLite-based implementation
  - PyArrow-based implementation
  - Other storage backends

**Core Functionality:**
- Collection/database of multiple series of market data:
  - Bars of instruments
  - Trade-ticks of instruments
  - Quote-ticks of instruments
- Standard feature: ability to add any market data into the storage
- Database-based implementations require `connect` and `disconnect` functions

**Storage Schema (SQLite example):**
- Separate table for Bars with reference to BarTypes table, which references Instrument
- Separate table for TradeTicks with reference to Instrument
- Separate table for QuoteTicks with reference to Instrument

**Deferred Considerations:**
- Data updates and corrections (use data as-is for now)
- Large dataset management and partitioning strategies
- Optimal database schema performance optimization

MarketDataStorage will be the primary source of historical data for strategies running in backtesting mode.

#### 1.3 MarketDataFeed

Generic interface to get any type of data in sorted order (by timestamp).

**Includes both:**
- Live data feeds
- Historical data feeds

**Interface Design:**
- Should be like Iterator where we can ask for next value
- Can provide mixed market data types from one stream (not tied to specific type)
- Can stream common market data: bars, quotes, trade-ticks
- **Extended Capability**: Can also provide other data types like NewsEvents

**Key Questions Addressed:**
- MarketDataFeed doesn't need to know total data point count
- Can provide mixed market data types in single stream
- Supports streaming mode (snapshot mode not needed)

**Deferred Challenges:**
- Feed disconnections and reconnections handling
- Buffering strategy for live feeds (when processing takes longer than data arrival)
- Data gap detection and handling

**Implementation Types:**
- CsvFile_BarsDataFeed
- CsvFile_TradeTicksDataFeed
- CsvFile_QuoteTicksDataFeed
- LiveBarsDataFeed
- LiveTradeTicksDataFeed
- LiveQuoteTicksDataFeed

**Synchronization:**
- Synchronizer component ensures market data published in correct order
- Supports bar/tick/quotes synchronization for multi-data strategies
- In backtest: next() pulls from historical arrays
- In live: next() might block until new tick arrives from socket
- Strategy doesn't know the difference

---

### Implement as 2nd things

#### 2.1 ExecutionEngine

**Purpose**: Processes orders + market-prices and generates Execution objects.

**Core Functionality:**
- Receives orders and market prices as input
- Generates simulated order-fills (Execution objects)
- Updates Order states and positions
- Handles partial and full fills

**Architecture Placement:**
- In live trading: handled by broker/brokerage services
- In backtesting: part of SimulatedBroker (BrokerageProvider instance)

**Realistic Trading Simulation Features:**
- **Network Delays**: Configurable delays for market data to simulate network latency
- **Slippage Modeling**: Market impact simulation through market depth prices
- **Advanced Order Types Support:**
  - OCO (One Cancels Other)
  - OUO (One Updates Other)
  - Bracket orders (optional)

**Key Relationship:**
- ExecutionEngine creates Execution objects
- Perfect naming consistency: ExecutionEngine → Execution
- Users immediately understand the connection

---

### Implement as 3rd things - Supported Workflows

#### 3.1 Backtesting Workflow

**Updated Process:**
1. Strategy subscribes to specific market-data (determines required data feeds)
2. Specify start + end datetime (backtesting period)
3. Use HistoricalClock set to start time
4. Use SimulatedBroker for order execution (contains ExecutionEngine)
5. Stream historical data into the strategy
6. Generate performance reports

#### 3.2 Live Trading Workflow

**Updated Four-Phase Process:**

**Phase A: Live Data Subscription**
- Subscribe to required live market data feeds
- Cache incoming live data for continuity after historical data processing

**Phase B: Historical Data Processing**
- Process historical data using HistoricalClock and SimulatedBroker
- SimulatedBroker uses ExecutionEngine to process orders against historical prices

**Phase C: Cached Data Processing**
- Process all cached live data using same HistoricalClock and SimulatedBroker
- ExecutionEngine continues processing orders against cached market data

**Phase D: Transition to Live**
- **Market Data Transition**: Automatic continuation from historical to live data when no more cached data
- **Broker Transition**: Not automatic - Strategy must allow switching to RealBroker
  - Existing positions (partially/fully filled) remain with SimulatedBroker
  - Unfilled entry orders can be migrated to RealBroker
  - All new entry orders/opportunities go to RealBroker only

**Execution Collection:**
- Executions collected cumulatively from both SimulatedBroker and RealBroker
- Each execution knows its broker source (Simulated vs Real)
- ExecutionEngine in SimulatedBroker generates simulated executions
- RealBroker receives actual executions from live broker

**Required Order/Opportunity Attributes:**
- Orders must know if they are ENTRY/EXIT orders
- Orders must know their broker assignment (Simulated vs Real)
- Opportunities must know their broker assignment
- Two brokers available simultaneously: SimulatedBroker and RealBroker

---

### Additional Components

#### 4.1 Strategy Performance Analysis

**Analyzer Component:**
- Strategy should have Analyzer component calculating PerformanceStatistics from Executions
- PerformanceStatistics calculated from all execution data
- **Filtering Capabilities:**
  - By trade direction (long/short trades)
  - By broker source (SimulatedBroker vs RealBroker)

**Integration:**
- PerformanceAnalyzer component constructs PerformanceStatistics object
- Strategy can request PerformanceStatistics anytime
- PerformanceStatistics objects can be combined for cumulative statistics
- Statistics updated incrementally after each execution
- Includes executions from both SimulatedBroker and RealBroker with broker identification flags

#### 4.2 BrokerageProvider

- Publishes order updates (changed order states)
- Publishes executions (order fills) for partial/full fills
- Provides Positions on request
- Publishes events: PositionChanged, PositionIncreased, PositionDecreased
- Connects using Account (not implemented yet)
- Provides Account info (funds, etc. - not implemented yet)

**Methods:**
- submit_order / cancel_order / update_order
- on_execution()
- get_positions()

**SimulatedBroker Implementation:**
- Contains ExecutionEngine component
- ExecutionEngine processes orders against market data
- Generates Execution objects for order fills
- Updates order states and positions

#### 4.3 Opportunity

Group consisting of:
- Entry order (required)
- Optional Profit order (submitted if entry filled) with optional management
- Optional Stoploss order (submitted if entry filled) with optional management

**States:**
- **Waiting**: Entry order not filled yet
- **InTrade**: Entry order partially/fully filled (position > 0)
- **Finished**: Entry cancelled before fill OR entry filled AND position == 0

Each Opportunity tied to specific broker (SimulatedBroker or RealBroker).

#### 4.4 Strategy

**Core Functions:**
- add_market_data_feed(MarketDataFeed, key) # key used as `self.data[key]`
- add_indicator()
- submit_order() / cancel_order()

**Performance Integration:**
- Built-in PerformanceAnalyzer component
- Real-time PerformanceStatistics access
- Incremental statistics updates after each execution
- Combined statistics from both SimulatedBroker and RealBroker executions
