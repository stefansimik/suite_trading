## Core Architectural Principles

### Unified Workflow Architecture

**Key Insight**: Backtesting is not a separate workflow - it's just Phase B of the complete Live Trading workflow.

**Workflow Unification**:
- **Backtesting**: Execute only Phase B (Historical Event Processing) and stop
- **Live Trading**: Execute Phase A (Live Event Processing) → Phase B (Historical Event Processing) → Phase C (Live Event Processing)
- **Same Components**: TradingEngine, EventFeeds, Strategy callbacks, execution logic
- **Same Event Flow**: Identical event object processing pipeline in both modes

**Event Type Consistency Guarantee**:
The architecture **guarantees** that strategies receive **exactly the same event object types** during historical processing (backtesting) as they subscribe to for live trading. The only difference is timestamps - historical objects have old timestamps, live objects have current timestamps.

**Implementation Benefits**:
- **Code Reuse**: Single TradingEngine handles all phases
- **Seamless Transitions**: No architectural changes between phases
- **Realistic Backtesting**: Historical processing uses exact same event object structures as live trading
- **Simplified Testing**: Test backtesting = test Phase B of live trading

---

## Implementation Plan

### Phase 1: Core Event Foundation

#### 1.2 EventFeed Interface (Protocol)

**Why Now**: Now that we have event objects, we can define how to produce them.

**Core Interface Design:**
- Simple event retrieval with `next() -> Optional[Event]`
- Performance optimization with `is_finished()` method
- No exceptions for normal flow control
- KISS principle: minimal complexity for common cases

**Interface Definition:**
```python
from typing import Protocol, Optional
from suite_trading.domain.event import Event

class EventFeed(Protocol):
    """Simple event feed interface with permanent closure detection."""

    def next(self) -> Optional[Event]:
        """Get the next event if available.

        Returns None if:
        - No event is currently available (live feeds)
        - Feed has no more data but is not permanently finished

        Returns:
            Event: Next event object, or None if no event available
        """
        ...

    def is_finished(self) -> bool:
        """Check if this feed is permanently closed.

        A finished feed will never produce events again and should be
        removed from active polling to improve performance.

        Returns:
            bool: True if feed is permanently closed, False otherwise
        """
        ...

    def get_event_types(self) -> list[str]:
        """Get list of event types this feed produces.

        Returns:
            list[str]: List of event type identifiers (e.g., ["bar", "tick"])
        """
        ...
```

**Usage Pattern:**
```python
# TradingEngine polling with performance optimization
def poll_feeds(self):
    """Poll all active feeds for new events."""
    # Check for finished feeds first (less frequent operation)
    for feed in list(self.active_feeds):
        if feed.is_finished():
            self.active_feeds.remove(feed)
            self.logger.info(f"Removed finished feed: {feed}")

    # Poll remaining active feeds for events
    for feed in self.active_feeds:
        event = feed.next()
        if event is not None:
            self.buffer_event(event)
```

**Implementation Examples:**

*Historical Feed (becomes finished):*
```python
class HistoricalBarFeed:
    def __init__(self, data_source):
        self.data_source = data_source
        self._finished = False

    def next(self) -> Optional[Event]:
        if self._finished:
            return None

        if self.data_source.has_more_data():
            return self.data_source.get_next_bar()
        else:
            self._finished = True
            return None

    def is_finished(self) -> bool:
        return self._finished
```

*Live Feed (never finished):*
```python
class LiveBarFeed:
    def next(self) -> Optional[Event]:
        if self.current_bar_complete():
            return self.get_completed_bar()
        return None

    def is_finished(self) -> bool:
        return False  # Live feeds are never finished
```

**Key Benefits:**
- **Ultra-Simple Common Case**: Just `event = feed.next(); if event: process(event)`
- **Performance Optimization**: Finished feeds can be removed from polling
- **Clear Semantics**: `next()` handles data availability, `is_finished()` handles permanent closure
- **No Exception Handling**: Normal flow uses simple None checks
- **KISS Principle**: Minimal additional complexity while solving performance problem

**Dependencies**: Requires Event abstract base class and concrete event objects

### Phase 2: Event Infrastructure

#### 2.1 MarketDataStorage Interface

**Why Now**: Storage interface for historical event objects we just defined.

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
- Collection/database of multiple series of market events:
  - Bars of instruments
  - Trade-ticks of instruments
  - Quote-ticks of instruments
- Standard feature: ability to add any market events into the storage
- Database-based implementations require `connect` and `disconnect` functions
- Return event objects that inherit from Event abstract base class
- Support for querying by time ranges and instruments

**Storage Schema (SQLite example):**
- Separate table for Bars with reference to BarTypes table, which references Instrument
- Separate table for TradeTicks with reference to Instrument
- Separate table for QuoteTicks with reference to Instrument

**Deferred Considerations:**
- Event updates and corrections (use events as-is for now)
- Large dataset management and partitioning strategies
- Optimal database schema performance optimization

MarketEventStorage will be the primary source of historical events for strategies running in backtesting mode.

**Dependencies**: Requires concrete event objects from Phase 1

#### 2.2 Historical EventFeed Implementations

**Why Now**: Concrete implementations that read from MarketEventStorage.

**Implementation Types:**
- HistoricalBarFeed
- HistoricalTradeFeed
- HistoricalQuoteFeed

**Dependencies**: Requires EventFeed interface and MarketEventStorage

#### 2.3 Live EventFeed Implementations

**Why Now**: Concrete implementations for live event sources.

**Implementation Types:**
- LiveBarFeed
- LiveTradeFeed
- LiveQuoteFeed
- Event feeds (OneTimeEvent, PeriodicEvent generators)
- Mixed event type feeds (bars + ticks + quotes in single stream)

**Dependencies**: Requires EventFeed interface and event objects

### Phase 3: Time and Event Management

#### 3.1 Event-Driven Time Management

**Why Now**: Now we can implement time management using our Event objects.

**Core Architecture Change**: No separate Clock system needed. Time management is event-driven based on timestamps in event objects.

**Key Principles:**
- **Backtesting Mode**: TradingEngine tracks latest datetime from historical event objects
- **Live Trading Mode**: Uses real-time clock automatically
- **Event-Driven Progression**: Time moves forward based on datetime timestamps in event objects from EventFeed(s)
- **UTC Standard**: All event objects must be in UTC format (EventFeed responsible for conversion)

**TradingEngine Responsibilities:**
- Track latest (current) datetime from processed event objects
- Buffer and sort all incoming event objects by datetime timestamps
- Distribute sorted event objects via MessageBus to other components
- Poll next event object from all EventFeed objects using `next()` method
- Sort Event objects using their `__lt__` method
- Track current time from `dt_event` timestamps
- Buffer and distribute event objects chronologically

**Time-Based Event Objects Support:**
- **OneTimeEvent**: Happens once at specific date/time
- **PeriodicEvent**: Happens regularly (every X seconds/minutes/milliseconds)
- Event objects generated by specialized EventFeed implementations
- Event objects treated like any other event objects (bars/ticks/quotes)

**Strategy Time Access:**
- Strategies have easy access to latest datetime
- Current time automatically reflects processing mode (backtesting vs live)

**Event Object Sorting Strategy:**
- TradingEngine sorts by appropriate datetime field (dt_received vs event time)
- Consistent sorting in both backtesting and live trading modes
- Must handle realistic event object arrival scenarios

**Dependencies**: Requires Event abstract base class and concrete implementations

#### 3.2 Delay Simulation Component

**Why Now**: Modifies `dt_received` timestamps on our Event objects.

**Purpose**: Central component to simulate realistic event delays for backtesting.

**Functionality:**
- Processes all incoming events before TradingEngine distribution
- Can modify `dt_received` timestamps to simulate network delays
- Configurable delay patterns for different event types
- Enables realistic backtesting scenarios with latency simulation
- Maintains Event abstract base class contract

**Integration:**
- All events flow through this component first
- TradingEngine receives delay-adjusted events
- Maintains consistency between backtesting and live trading behavior

**Dependencies**: Requires Event objects and time management

### Phase 4: Strategy Integration

#### 4.1 Strategy Callback System

**Why Now**: Now we can route our concrete Event objects to strategy methods.

**Core Event Handling:**
- All events coming to Strategy must be catchable in `on_event` method
- Universal entry point for any event type from EventFeeds

**Event Distribution Logic:**
- `distribute_event_to_proper_callbacks` method checks event type
- Routes common event types to specific callback methods
- Ensures both universal and specific handling

**Specific Callback Methods:**
- `on_bar`: Called for Bar event objects
- `on_trade_tick`: Called for TradeTick event objects
- `on_quote_tick`: Called for QuoteTick event objects
- `on_time_event`: Called for OneTimeEvent and PeriodicEvent objects

**Implementation**:
- `on_event(event: Event)` - universal handler
- `on_bar(bar: Bar)` - specific handler
- `on_trade_tick(tick: TradeTick)` - specific handler
- `on_quote_tick(tick: QuoteTick)` - specific handler

**Design Principle:**
- ANY event coming to strategy is first caught by `on_event`
- Most common event types also trigger their specific callbacks
- Strategy can choose to handle events universally or specifically
- Maintains flexibility while providing convenience methods

**Dependencies**: Requires all concrete event objects

#### 4.2 TradingEngine Core

**Why Now**: Orchestrates EventFeeds, time management, and strategy callbacks.

**Core Functions**:
- Poll events from multiple EventFeeds
- Sort and distribute Event objects
- Manage strategy subscriptions
- Coordinate time progression

**Dependencies**: Requires EventFeeds, time management, and callback system

### Phase 5: Execution Layer

#### 5.1 Order and Execution Objects

**Why Now**: Define trading execution data structures.

**Objects**:
- Order (with states)
- Execution
- Position

**Dependencies**: Minimal - mostly independent domain objects

#### 5.2 ExecutionEngine

**Why Now**: Processes orders against market events to generate executions.

**Purpose**: Processes orders + market-prices and generates Execution objects.

**Core Functionality:**
- Receives orders and market prices as input
- Generates simulated order-fills (Execution objects)
- Updates Order states and positions
- Handles partial and full fills
- Receives Order objects and Event objects
- Generates Execution objects
- Updates Order states and Positions

**Architecture Placement:**
- In live trading: handled by broker/brokerage services
- In backtesting: part of SimulatedBroker (BrokerageProvider instance)

**Realistic Trading Simulation Features:**
- **Network Delays**: Configurable delays for market events to simulate network latency
- **Slippage Modeling**: Market impact simulation through market depth prices
- **Advanced Order Types Support:**
  - OCO (One Cancels Other)
  - OUO (One Updates Other)
  - Bracket orders (optional)

**Key Relationship:**
- ExecutionEngine creates Execution objects
- Perfect naming consistency: ExecutionEngine → Execution
- Users immediately understand the connection

**Dependencies**: Requires Event objects, Order/Execution objects

#### 5.3 BrokerageProvider (SimulatedBroker)

**Why Now**: Contains ExecutionEngine and manages order lifecycle.

**Functionality:**
- Order submission and management
- Contains ExecutionEngine
- Position tracking
- Execution publishing

**Dependencies**: Requires ExecutionEngine and order objects

### Phase 6: Unified Workflows

#### 6.1 Backtesting Workflow

**Why Now**: Combines all components for historical event processing.

**Process Overview:**
Backtesting executes **only Phase B** of the complete Live Trading workflow and then stops.

**Event-Driven Process:**
1. Strategy subscribes to specific market events (determines required EventFeeds)
2. Specify start + end datetime (backtesting period)
3. TradingEngine creates historical EventFeeds from MarketEventStorage for **same event types**
4. TradingEngine polls events from all EventFeeds using `next()` method
5. Events sorted by datetime and distributed via MessageBus
6. Time progresses automatically based on event timestamps
7. Use SimulatedBroker for order execution (contains ExecutionEngine)
8. Strategy receives events through **same callback system** (`on_event`, `on_bar`, etc.)
9. Generate performance reports

**Key Features:**
- **Identical to Phase B**: Same components, same event flow as live trading Phase B
- **Event Type Consistency**: Strategy receives exact same event objects as in live trading
- **Time Management**: Event-driven progression using historical timestamps
- **Realistic Execution**: SimulatedBroker with ExecutionEngine processes orders

**Components Used:**
- Historical EventFeeds
- TradingEngine
- SimulatedBroker
- Strategy callbacks

**Dependencies**: Requires all previous components

#### 6.2 Live Trading Workflow

**Why Now**: Extends backtesting with live events and real broker integration.

**Event Type Consistency Implementation:**

**Strategy Subscription Drives Event Requirements:**
The workflow ensures perfect event type consistency through this process:

1. **Strategy subscribes** to specific market event types (e.g., bars, trade ticks, quote ticks)
2. **TradingEngine creates corresponding EventFeeds** from appropriate sources:
   - **Historical Mode**: EventFeeds from MarketEventStorage for same event types
   - **Live Mode**: EventFeeds from live sources for same event types
3. **Same callback system** handles both historical and live events through identical methods
4. **Same event objects** flow through strategy (Bar, TradeTick, QuoteTick, etc.)

**Architectural Guarantees:**
- **Universal Event Interface**: All event objects inherit from the same `Event` abstract base class
- **Identical EventFeed Interface**: Historical and live EventFeeds use same `next()` method
- **Same Callback Methods**: `on_bar()`, `on_trade_tick()`, `on_quote_tick()` work identically
- **MarketEventStorage Contract**: Must return same event object types as live feeds provide

**Four-Phase Unified Process:**

**Phase A: Live Event Subscription**
- Subscribe to required live EventFeeds for **same event types** as strategy subscribed to
- Cache incoming live events for continuity after historical event processing
- **Event Consistency**: Live EventFeeds produce same event object types (Bar, TradeTick, etc.)

**Phase B: Historical Event Processing** *(Identical to Backtesting)*
- **Same Process**: Identical to standalone backtesting workflow
- **Same Components**: TradingEngine, historical EventFeeds, SimulatedBroker, ExecutionEngine
- **Same Event Types**: Strategy receives identical event objects as in backtesting
- **Same Callbacks**: `on_bar()`, `on_trade_tick()`, `on_quote_tick()` work identically
- **Event-Driven Time**: Time progression based on historical event timestamps
- **Purpose**: Strategy warmup and historical performance validation

**Phase C: Cached Event Processing**
- **Seamless Continuation**: Process cached live events using same event-driven approach
- **Same Event Objects**: Cached events produce same Bar, TradeTick, QuoteTick objects
- **Same Processing**: TradingEngine continues with identical event handling logic
- **Bridge Function**: Connects historical events to live events without gaps

**Phase D: Live Trading Execution**
- **Market Event Transition**: Automatic continuation from cached to live EventFeeds
- **Event Consistency**: Live EventFeeds produce same event object types as previous phases
- **Time Management**: Switches from event-driven to real-time automatically
- **Broker Transition**: Strategy-controlled switching to RealBroker
  - Existing positions remain with SimulatedBroker
  - New opportunities can use RealBroker
  - Dual broker execution support

**Unified Event Flow Guarantee:**
```
Strategy Subscription → Same Event Types → All Phases
     ↓                       ↓              ↓
  subscribe_to_bars()  →  Bar objects  →  Phase B, C, D
  subscribe_to_ticks() → TradeTick objs →  Phase B, C, D
```

**Execution Collection:**
- Cumulative executions from both SimulatedBroker and RealBroker
- Each execution tagged with broker source (Simulated vs Real)
- Unified performance analysis across all phases
- Seamless transition tracking

**Additional Components:**
- Live EventFeeds
- RealBroker integration
- Multi-phase execution

**Dependencies**: Requires backtesting workflow as foundation

---

## Supporting Components

These components support and extend the core implementation phases but can be developed in parallel or after the main phases are complete.

### Strategy Performance Analysis

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

**Dependencies**: Requires Execution objects and BrokerageProvider

### BrokerageProvider Extensions

**Additional Functionality** (extends Phase 5.3):
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
- ExecutionEngine processes orders against market events
- Generates Execution objects for order fills
- Updates order states and positions

**Dependencies**: Requires Phase 5 (Execution Layer) completion

### Opportunity Management

**Opportunity Concept:**
Group consisting of:
- Entry order (required)
- Optional Profit order (submitted if entry filled) with optional management
- Optional Stoploss order (submitted if entry filled) with optional management

**States:**
- **Waiting**: Entry order not filled yet
- **InTrade**: Entry order partially/fully filled (position > 0)
- **Finished**: Entry cancelled before fill OR entry filled AND position == 0

Each Opportunity tied to specific broker (SimulatedBroker or RealBroker).

**Dependencies**: Requires Order objects and BrokerageProvider

### Strategy Implementation

**Core Functions:**
- add_event_feed(EventFeed, key) # key used as `self.events[key]`
- add_indicator()
- submit_order() / cancel_order()
- get_current_time() # Access to latest datetime from TradingEngine

**Event Callback System** (implements Phase 4.1):
- `on_event(event)`: Universal callback for any event type from EventFeeds
- `distribute_event_to_proper_callbacks(event)`: Routes events to specific callbacks
- `on_bar(bar)`: Specific callback for Bar event objects
- `on_trade_tick(tick)`: Specific callback for TradeTick event objects
- `on_quote_tick(tick)`: Specific callback for QuoteTick event objects
- `on_time_event(event)`: Specific callback for OneTimeEvent/PeriodicEvent objects

**Performance Integration:**
- Built-in PerformanceAnalyzer component
- Real-time PerformanceStatistics access
- Incremental statistics updates after each execution
- Combined statistics from both SimulatedBroker and RealBroker executions

**Time Management:**
- Easy access to current datetime through TradingEngine
- Time automatically reflects processing mode (backtesting vs live)
- No manual time management required

**Dependencies**: Requires Phase 4 (Strategy Integration) and supporting components

---

## Implementation Benefits

### Key Benefits of This Order

#### 1. **Natural Dependencies**
Each step builds on previous steps without circular dependencies.

#### 2. **Testable Increments**
You can test each component in isolation as you build it.

#### 3. **Clear Contracts**
Interfaces are defined before implementations, ensuring clean contracts.

#### 4. **Logical Progression**
Follows the natural flow: Event → Storage → Feeds → Processing → Execution → Workflows

#### 5. **Early Validation**
Core event structures are validated early before complex orchestration logic.

This order ensures that each implementation step has all its dependencies already in place, making development smoother and more logical.
