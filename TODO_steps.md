# Implementation Plan for Strategy Market Data Subscription and Order Execution

## Missing Components to Implement

### Phase 1: Core Protocols and Interfaces ✅ COMPLETED

#### Step 1.1: Create MarketDataProvider Protocol ✅ COMPLETED
**File**: `src/suite_trading/platform/market_data/market_data_provider.py`
**Dependencies**: None (uses existing domain objects)
**Purpose**: Define the unified interface for all market data requests

#### Step 1.2: Create Broker Protocol ✅ COMPLETED
**File**: `src/suite_trading/platform/broker/broker.py`
**Purpose**: Define unified interface for all broker implementations with connection management and comprehensive order handling

### Phase 2: TradingEngine Foundation

#### Step 2.1: Add Market Data Provider Integration to TradingEngine ✅ COMPLETED

#### Step 2.2: Add Broker Management to TradingEngine ✅ COMPLETED
**File**: `src/suite_trading/platform/engine/trading_engine.py` (modify existing)
**Dependencies**: Broker protocol
**Purpose**: Enable TradingEngine to manage multiple brokers and handle order operations

#### Step 2.3: Add MessageBus Integration for Data Distribution
**File**: `src/suite_trading/platform/engine/trading_engine.py` (modify existing)
**Dependencies**: MessageBus, updated NewBarEvent with `is_historical` attribute
**Purpose**: Implement MessageBus integration to deliver market data to subscribed strategies with proper data type context

Key requirements:
- Use MessageBus to distribute market data events to subscribed strategies
- Ensure proper handling of `is_historical` flag in data delivery
- Maintain data continuity between historical and live data feeds
- Support multiple strategies with different data subscription needs
- Create NewBarEvent with `is_historical=True` for historical data
- Create NewBarEvent with `is_historical=False` for live data

### Phase 3: Strategy Interface Enhancement

#### Step 3.1: Add Market Data Request Methods to Strategy
**File**: `src/suite_trading/strategy/base.py` (modify existing)
**Dependencies**: TradingEngine with market data provider integration (Step 2.1)
**Purpose**: Add market data request methods that delegate to TradingEngine

Key additions:
- `get_historical_bars_series(bar_type: BarType, from_dt: datetime, until_dt: Optional[datetime] = None) -> Sequence[Bar]` - delegate to engine
- `stream_historical_bars(bar_type: BarType, from_dt: datetime, until_dt: Optional[datetime] = None) -> None` - delegate to engine
- `subscribe_to_live_bars(bar_type: BarType) -> None` - delegate to engine
- `subscribe_to_live_bars_with_history(bar_type: BarType, history_days: int) -> None` - delegate to engine
- `unsubscribe_from_live_bars(bar_type: BarType) -> None` - delegate to engine

#### Step 3.2: Update Market Data Callback Methods in Strategy
**File**: `src/suite_trading/strategy/base.py` (modify existing)
**Dependencies**: Updated domain objects, NewBarEvent with `is_historical` attribute
**Purpose**: Update callback methods to handle historical vs live data context

Key updates:
- `on_bar(self, bar: Bar, is_historical: bool)` - replace existing `on_bar`
- `on_trade_tick(self, tick: TradeTick, is_historical: bool)` - update existing
- `on_quote_tick(self, tick: QuoteTick, is_historical: bool)` - update existing
- `on_historical_bars_series(self, bars: Sequence[Bar])` - new callback for series data

#### Step 3.3: Add Order Management Methods to Strategy
**File**: `src/suite_trading/strategy/base.py` (modify existing)
**Dependencies**: TradingEngine with broker management (Step 2.2)
**Purpose**: Add order management capabilities that delegate to TradingEngine

Key additions:
- `submit_order(self, order: Order, broker: Broker = broker.SIM) -> None` - delegate to engine
- `cancel_order(self, order: Order, broker: Broker = broker.SIM) -> None` - delegate to engine
- `modify_order(self, order: Order, broker: Broker = broker.SIM) -> None` - delegate to engine
- `get_active_orders(self, broker: Broker = broker.SIM) -> List[Order]` - delegate to engine

### Phase 4: Enhanced Domain Objects

#### Step 4.1: Update NewBarEvent with Historical Context
**File**: `src/suite_trading/domain/events/new_bar_event.py` (modify existing)
**Dependencies**: None (standalone domain object)
**Purpose**: Add `is_historical` attribute to support data context awareness

Key changes:
```python
# Updated constructor signature
def __init__(self,
             bar: Bar,
             dt_received: datetime,
             is_historical: bool = True):

# New property for accessing historical context
@property
def is_historical(self) -> bool:
    """Get whether this bar data is historical or live."""
    return self._is_historical
```

### Implementation Notes

**Dependency Flow:**
1. **Phase 1**: Protocols define interfaces (already completed)
2. **Phase 2**: TradingEngine implements core functionality using protocols
3. **Phase 3**: Strategy methods delegate to TradingEngine methods
4. **Phase 4**: Domain objects support the enhanced functionality

**Atomic Implementation:**
- Each step can be completed independently
- No forward dependencies between steps
- Each step builds on previously completed functionality
- Testing can be done incrementally after each step

**Key Benefits:**
- **Bottom-up approach**: Build foundation first, then higher-level interfaces
- **Testable increments**: Each step produces working, testable code
- **Clear dependencies**: Each step only depends on previously completed work
- **Maintainable structure**: Logical separation of concerns across layers
