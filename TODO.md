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

#### 1.1 Event Interface (Protocol)

**Why First**: This is the fundamental contract that all event objects must follow.

**Event Interface Specification:**
All event objects coming from outside world to TradingEngine must implement the `Event` interface:

```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol, runtime_checkable

@runtime_checkable
class Event(Protocol):
    """Protocol for all event objects entering the TradingEngine from external sources.

    This interface ensures consistent structure for event object handling, sorting, and processing
    across different object types (bars, ticks, quotes, time events, etc.).

    All event objects must be sortable to enable correct chronological processing order.
    """

    @property
    @abstractmethod
    def dt_received(self) -> datetime:
        """Datetime when the event object entered our system.

        This includes network latency and represents when the event was actually
        received by our trading system, not when it was originally created.
        Must be timezone-aware (UTC required).

        Returns:
            datetime: The timestamp when event was received by our system.
        """
        ...

    @property
    @abstractmethod
    def dt_event(self) -> datetime:
        """Event datetime when the event occurred, independent from arrival time.

        This represents the official time for the event (e.g., bar end-time,
        tick timestamp, quote timestamp) and is independent of network delays
        or when the event arrived in our system.
        Must be timezone-aware (UTC required).

        Returns:
            datetime: The event timestamp.
        """
        ...

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Type identifier for the event object.

        Used for easy type distinction and routing to appropriate handlers.
        Should be a simple string identifier like "bar", "trade_tick",
        "quote_tick", "time_event", etc.

        Returns:
            str: The type identifier for this event object.
        """
        ...

    def __lt__(self, other: 'Event') -> bool:
        """Enable sorting by event datetime for chronological processing.

        Event objects are sorted primarily by dt_event to ensure correct
        chronological processing order. If dt_event is equal, sort by
        dt_received as secondary criterion.

        Args:
            other (Event): Another event object to compare with.

        Returns:
            bool: True if this event object should be processed before other.
        """
        if self.dt_event != other.dt_event:
            return self.dt_event < other.dt_event
        return self.dt_received < other.dt_received
```

**Dependencies**: None - this is pure interface definition

#### 1.2 Core Event Objects Implementation

**Why Second**: Implement all concrete event types that will flow through the system.

**Implementation Order**:
1. **Bar** - implements Event interface
2. **TradeTick** - implements Event interface
3. **QuoteTick** - implements Event interface
4. **TimeEvent** (OneTimeEvent, RepeatingEvent) - implements Event interface

**Implementation Requirements:**
- All market data classes must implement the Event interface
- New event types (custom objects) must implement this interface
- TradingEngine will sort all incoming event objects using the comparison method
- Processing order: sorted by dt_event first, then by dt_received

**Event Object Requirements:**
All objects from EventFeed must have:
- `dt_received`: When object entered our system (includes network latency simulation)
- Event datetime: Official time for the object (e.g., bar end-time)
- Object type identifier for easy type distinction

**Dependencies**: Requires Event interface from step 1.1

#### 1.3 EventFeed Interface (Protocol)

**Why Third**: Now that we have event objects, we can define how to produce them.

**Core Interface Design:**
- Python Iterator-like interface with `next()` method
- Must know when finished (similar to Python Iterator)
- Must declare types of event objects it returns
- Access to last processed time for object generation

```python
class EventFeed(Protocol):
    def next(self) -> Event | None: ...
    def has_next(self) -> bool: ...
    def get_event_types(self) -> list[str]: ...
```

**Dependencies**: Requires Event interface and concrete event objects

### Phase 2: Event Infrastructure

#### 2.1 MarketDataStorage Interface

**Why Fourth**: Storage interface for historical event objects we just defined.

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
- Return event objects that implement Event interface
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

**Why Fifth**: Concrete implementations that read from MarketEventStorage.

**Implementation Types:**
- HistoricalBarFeed
- HistoricalTradeFeed
- HistoricalQuoteFeed

**Dependencies**: Requires EventFeed interface and MarketEventStorage

#### 2.3 Live EventFeed Implementations

**Why Sixth**: Concrete implementations for live event sources.

**Implementation Types:**
- LiveBarFeed
- LiveTradeFeed
- LiveQuoteFeed
- Event feeds (OneTimeEvent, RepeatingEvent generators)
- Mixed event type feeds (bars + ticks + quotes in single stream)

**Dependencies**: Requires EventFeed interface and event objects

### Phase 3: Time and Event Management

#### 3.1 Event-Driven Time Management

**Why Seventh**: Now we can implement time management using our Event objects.

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
- **RepeatingEvent**: Happens regularly (every X seconds/minutes/milliseconds)
- Event objects generated by specialized EventFeed implementations
- Event objects treated like any other event objects (bars/ticks/quotes)

**Strategy Time Access:**
- Strategies have easy access to latest datetime
- Current time automatically reflects processing mode (backtesting vs live)

**Event Object Sorting Strategy:**
- TradingEngine sorts by appropriate datetime field (dt_received vs event time)
- Consistent sorting in both backtesting and live trading modes
- Must handle realistic event object arrival scenarios

**Dependencies**: Requires Event interface and concrete implementations

#### 3.2 Delay Simulation Component

**Why Eighth**: Modifies `dt_received` timestamps on our Event objects.

**Purpose**: Central component to simulate realistic event delays for backtesting.

**Functionality:**
- Processes all incoming events before TradingEngine distribution
- Can modify `dt_received` timestamps to simulate network delays
- Configurable delay patterns for different event types
- Enables realistic backtesting scenarios with latency simulation
- Maintains Event interface contract

**Integration:**
- All events flow through this component first
- TradingEngine receives delay-adjusted events
- Maintains consistency between backtesting and live trading behavior

**Dependencies**: Requires Event objects and time management

### Phase 4: Strategy Integration

#### 4.1 Strategy Callback System

**Why Ninth**: Now we can route our concrete Event objects to strategy methods.

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
- `on_time_event`: Called for OneTimeEvent and RepeatingEvent objects

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

**Why Tenth**: Orchestrates EventFeeds, time management, and strategy callbacks.

**Core Functions**:
- Poll events from multiple EventFeeds
- Sort and distribute Event objects
- Manage strategy subscriptions
- Coordinate time progression

**Dependencies**: Requires EventFeeds, time management, and callback system

### Phase 5: Execution Layer

#### 5.1 Order and Execution Objects

**Why Eleventh**: Define trading execution data structures.

**Objects**:
- Order (with states)
- Execution
- Position

**Dependencies**: Minimal - mostly independent domain objects

#### 5.2 ExecutionEngine

**Why Twelfth**: Processes orders against market events to generate executions.

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

**Why Thirteenth**: Contains ExecutionEngine and manages order lifecycle.

**Functionality:**
- Order submission and management
- Contains ExecutionEngine
- Position tracking
- Execution publishing

**Dependencies**: Requires ExecutionEngine and order objects

### Phase 6: Unified Workflows

#### 6.1 Backtesting Workflow

**Why Fourteenth**: Combines all components for historical event processing.

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

**Why Fifteenth**: Extends backtesting with live events and real broker integration.

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
- **Universal Event Interface**: All event objects implement the same `Event` protocol
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
- `on_time_event(event)`: Specific callback for OneTimeEvent/RepeatingEvent objects

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
